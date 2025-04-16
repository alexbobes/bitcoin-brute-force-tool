// Utility functions
function humanFormat(number) {
    let magnitude = 0;
    while (Math.abs(number) >= 1000) {
        magnitude += 1;
        number /= 1000.0;
    }
    return number.toFixed(2) + ' ' + ['', 'K', 'M', 'B', 'T'][magnitude];
}

function formatTimestamp() {
    const now = new Date();
    return now.toISOString().replace('T', ' ').substring(0, 19);
}

function addLogEntry(message) {
    const logContainer = document.getElementById('statusLog');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    const timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = formatTimestamp();
    
    const messageSpan = document.createElement('span');
    messageSpan.className = 'message';
    messageSpan.textContent = message;
    
    entry.appendChild(timestamp);
    entry.appendChild(messageSpan);
    
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;
    
    // Limit log entries to avoid performance issues
    const maxEntries = 50;
    while (logContainer.children.length > maxEntries) {
        logContainer.removeChild(logContainer.firstChild);
    }
}

// Initialize hash rate and ETA estimates
let lastTotalAddresses = 0;
let lastTimestamp = Date.now();
let addressesHistory = [];
const maxHistoryPoints = 10;

// Data update functions
function updateDashboard() {
    const now = Date.now();
    
    // Fetch hash rate from API directly
    fetch('/api/hash-rate')
        .then(response => response.json())
        .then(data => {
            const hashRate = parseFloat(data.hash_rate) || 0;
            document.getElementById('hashRate').textContent = hashRate.toFixed(2) + ' keys/sec';
            
            // Log first hash rate update
            if (!window.initialHashRateLogged && hashRate > 0) {
                window.initialHashRateLogged = true;
                addLogEntry(`Initial hash rate: ${hashRate.toFixed(2)} keys/sec`);
            }
            
            // Log significant changes (only if we have actual data)
            if (window.lastHashRate && Math.abs(hashRate - window.lastHashRate) / Math.max(window.lastHashRate, 1) > 0.25) {
                addLogEntry(`Hash rate changed to ${hashRate.toFixed(2)} keys/sec`);
            }
            
            window.lastHashRate = hashRate;
        })
        .catch(error => {
            console.error('Error fetching hash rate:', error);
        });
    
    // Force a cache-busting fetch for the total addresses
    fetch('/api/total-addresses?_=' + new Date().getTime())
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Ensure we have a valid number
            const totalAddresses = parseInt(data.total_addresses);
            
            // Only update if we have a valid value
            if (!isNaN(totalAddresses) && totalAddresses > 0) {
                // Update the display
                document.getElementById('totalAddresses').textContent = humanFormat(totalAddresses);
                
                // Log when the value changes significantly
                if (window.lastTotalAddresses && 
                    Math.abs(totalAddresses - window.lastTotalAddresses) > 1000000) {
                    addLogEntry(`Significant progress: Now at ${humanFormat(totalAddresses)} addresses`);
                }
                
                // Update chart if it exists
                if (typeof mainChart !== 'undefined') {
                    mainChart.data.datasets[0].data[1] = totalAddresses;
                    mainChart.update();
                }
                
                // Only log occasionally 
                if (Math.random() < 0.1) {  // 10% chance
                    addLogEntry(`Processed ${humanFormat(totalAddresses)} addresses so far`);
                }
                
                // Store for next comparison
                lastTotalAddresses = totalAddresses;
                lastTimestamp = now;
            } else {
                console.warn("Received invalid total addresses:", data.total_addresses);
                if (!window.addressErrorLogged) {
                    addLogEntry("Warning: Received invalid address count from server");
                    window.addressErrorLogged = true;
                }
            }
            
            // Update timestamp regardless
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
            
            // Calculate ETA based on latest data
            fetch('/api/hash-rate')
                .then(response => response.json())
                .then(rateData => {
                    updateETA(rateData.hash_rate, lastTotalAddresses || 0);
                })
                .catch(error => {
                    console.error("Error fetching hash rate for ETA:", error);
                });
        })
        .catch(error => {
            console.error('Error fetching total addresses:', error);
            addLogEntry('Error updating statistics: ' + error.message);
        });
    
    // Update additional stats with cache-busting
    fetch('/api/total-to-bruteforce?_=' + new Date().getTime())
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Parse the value, ensuring it's a valid number
            const totalToBruteforce = parseInt(data.total_to_bruteforce);
            
            if (!isNaN(totalToBruteforce) && totalToBruteforce > 0) {
                // Update display
                document.getElementById('totalAddressesToBruteforce').textContent = humanFormat(totalToBruteforce);
                
                // Store for future reference
                window.cachedTotalToBruteforce = totalToBruteforce;
                
                // Update chart
                if (typeof mainChart !== 'undefined') {
                    mainChart.data.datasets[0].data[0] = totalToBruteforce;
                    mainChart.update();
                }
                
                // Only proceed if we have valid address counts
                if (typeof lastTotalAddresses === 'number' && lastTotalAddresses > 0) {
                    // Calculate progress percentage
                    let progressPercent = Math.min(100, (lastTotalAddresses / totalToBruteforce) * 100);
                    progressPercent = Math.max(0, progressPercent); // Ensure non-negative
                    
                    // Only proceed if value is valid
                    if (!isNaN(progressPercent)) {
                        // Update UI elements
                        document.getElementById('progressBar').style.width = progressPercent.toFixed(2) + '%';
                        document.getElementById('progressPercent').textContent = progressPercent.toFixed(2) + '%';
                        
                        // Log initial progress once
                        if (window.initialProgressLogged !== true) {
                            window.initialProgressLogged = true;
                            addLogEntry(`Current progress: ${progressPercent.toFixed(2)}% complete`);
                        }
                        
                        // Log milestone progress (multiples of 10%)
                        if (Math.floor(progressPercent) % 10 === 0 && progressPercent > 0) {
                            const milestone = Math.floor(progressPercent);
                            if (!window.lastMilestone || window.lastMilestone !== milestone) {
                                window.lastMilestone = milestone;
                                addLogEntry(`Reached ${milestone}% completion milestone`);
                            }
                        }
                    } else {
                        console.warn("Progress calculation resulted in NaN");
                    }
                }
            } else {
                console.warn("Received invalid totalToBruteforce:", data.total_to_bruteforce);
                
                // Use cached value if available
                if (window.cachedTotalToBruteforce) {
                    document.getElementById('totalAddressesToBruteforce').textContent = 
                        humanFormat(window.cachedTotalToBruteforce);
                }
            }
        })
        .catch(error => {
            console.error('Error fetching total to bruteforce:', error);
            
            // Use cached value if available
            if (window.cachedTotalToBruteforce) {
                document.getElementById('totalAddressesToBruteforce').textContent = 
                    humanFormat(window.cachedTotalToBruteforce);
            } else {
                document.getElementById('totalAddressesToBruteforce').textContent = 'Error';
            }
            
            // Set fallback UI in case of error
            if (!window.progressErrorLogged) {
                window.progressErrorLogged = true;
                addLogEntry('Error calculating progress: ' + error.message);
            }
        });
    
    // Update found addresses count with cache-busting
    fetch('/api/total-found?_=' + new Date().getTime())
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const totalFound = parseInt(data.total_found);
            
            if (!isNaN(totalFound)) {
                // Update display with proper formatting
                document.getElementById('totalFound').textContent = humanFormat(totalFound);
                
                // Store for future reference
                window.cachedTotalFound = totalFound;
                
                // Update chart
                if (typeof mainChart !== 'undefined') {
                    mainChart.data.datasets[0].data[2] = totalFound;
                    mainChart.update();
                }
                
                // Initial logging of found count (once only)
                if (window.foundCountLogged !== true) {
                    window.foundCountLogged = true;
                    if (totalFound > 0) {
                        addLogEntry(`Currently found ${totalFound} matching address${totalFound > 1 ? 'es' : ''}`);
                    } else {
                        addLogEntry('No matching addresses found yet');
                    }
                }
                
                // Add log entry if new addresses are found (high priority notification)
                if (typeof window.lastFoundCount === 'number' && 
                    totalFound > window.lastFoundCount) {
                    const newFound = totalFound - window.lastFoundCount;
                    addLogEntry(`🎉 Found ${newFound} new matching address${newFound > 1 ? 'es' : ''}! 🎉`);
                }
                
                // Update stored value for next comparison
                window.lastFoundCount = totalFound;
            } else {
                console.warn("Received invalid totalFound:", data.total_found);
                
                // Use cached value if available
                if (typeof window.cachedTotalFound === 'number') {
                    document.getElementById('totalFound').textContent = 
                        humanFormat(window.cachedTotalFound);
                }
            }
        })
        .catch(error => {
            console.error('Error fetching total found:', error);
            
            // Use cached value if available
            if (typeof window.cachedTotalFound === 'number') {
                document.getElementById('totalFound').textContent = 
                    humanFormat(window.cachedTotalFound);
            } else {
                document.getElementById('totalFound').textContent = '0';
            }
            
            if (!window.foundErrorLogged) {
                window.foundErrorLogged = true;
                addLogEntry('Error updating found addresses: ' + error.message);
            }
        });
}

function updateETA(rate, currentTotal) {
    // Use cached totalToBruteforce value if available to avoid another fetch
    if (window.cachedTotalToBruteforce && rate > 0 && currentTotal >= 0) {
        calculateAndDisplayETA(rate, currentTotal, window.cachedTotalToBruteforce);
    } else {
        // Otherwise fetch fresh data with cache-busting
        fetch('/api/total-to-bruteforce?_=' + new Date().getTime())
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const totalToBruteforce = parseInt(data.total_to_bruteforce);
                
                if (!isNaN(totalToBruteforce) && totalToBruteforce > 0) {
                    // Store for future reference
                    window.cachedTotalToBruteforce = totalToBruteforce;
                    
                    // Calculate and display ETA
                    calculateAndDisplayETA(rate, currentTotal, totalToBruteforce);
                } else {
                    document.getElementById('progressETA').textContent = 'Calculating...';
                }
            })
            .catch(error => {
                console.error('Error calculating ETA:', error);
                document.getElementById('progressETA').textContent = 'N/A';
            });
    }
}

// Helper function to calculate and display ETA
function calculateAndDisplayETA(rate, currentTotal, totalToBruteforce) {
    // Only calculate if we have valid data and non-zero rate
    if (rate > 0 && totalToBruteforce > 0 && currentTotal >= 0) {
        // Calculate remaining addresses (ensure it's positive)
        const remainingAddresses = Math.max(0, totalToBruteforce - currentTotal);
        
        // Only display ETA if there are addresses remaining
        if (remainingAddresses > 0) {
            const remainingSeconds = remainingAddresses / rate;
            
            // Format ETA
            const etaText = formatETA(remainingSeconds);
            document.getElementById('progressETA').textContent = etaText;
            
            // Log significant ETA changes
            if (!window.lastETATime || Math.abs(remainingSeconds - window.lastETATime) > 86400) {
                // Only log if ETA changed by more than a day
                window.lastETATime = remainingSeconds;
                addLogEntry(`Estimated completion time: ${etaText}`);
            }
        } else {
            document.getElementById('progressETA').textContent = 'Complete';
        }
    } else {
        document.getElementById('progressETA').textContent = 'Calculating...';
    }
}

function formatETA(seconds) {
    if (seconds === Infinity || isNaN(seconds)) {
        return 'N/A';
    }
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 365) {
        const years = (days / 365).toFixed(1);
        return `${years} years`;
    } else if (days > 30) {
        const months = (days / 30).toFixed(1);
        return `${months} months`;
    } else if (days > 0) {
        return `${days}d ${hours}h`;
    } else if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes} minutes`;
    }
}

// Add API endpoint for found addresses
function fetchTotalFound() {
    return fetch('/api/total-found')
        .then(response => response.json())
        .catch(error => {
            console.error('Error fetching total found:', error);
            return { total_found: 0 };
        });
}

// Initialize dashboard
window.addEventListener('DOMContentLoaded', () => {
    // Add initial log entry
    addLogEntry('Dashboard initialized');
    
    // Initial load of data
    updateDashboard();
    
    // Set up regular refresh with error handling
    const updateInterval = setInterval(() => {
        try {
            updateDashboard();
        } catch (e) {
            console.error('Error during dashboard update:', e);
            addLogEntry('Error refreshing data: ' + e.message);
        }
    }, 5000);
    
    // Force a full refresh periodically to ensure data stays fresh
    setInterval(() => {
        try {
            // Clear any cached data
            window.lastTotalAddresses = null;
            window.lastFoundCount = null;
            window.lastHashRate = null;
            
            // Force a full dashboard refresh
            updateDashboard();
            addLogEntry('Performed full data refresh');
        } catch (e) {
            console.error('Error during full refresh:', e);
        }
    }, 60000); // Full refresh every minute
    
    // Set up event handling for chart type switching
    if (document.getElementById('showBarChart')) {
        document.getElementById('showBarChart').addEventListener('click', function() {
            addLogEntry('Switched to bar chart view');
        });
    }
    
    if (document.getElementById('showLineChart')) {
        document.getElementById('showLineChart').addEventListener('click', function() {
            addLogEntry('Switched to line chart view');
        });
    }
});
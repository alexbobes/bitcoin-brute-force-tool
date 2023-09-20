var dailyChart = new Chart(document.getElementById('dailyChart').getContext('2d'), {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: '# of Addresses Processed Daily',
            data: [],
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            borderColor: 'rgba(75, 192, 192, 1)',
            borderWidth: 1
        }]
    },
    options: {
        scales: {
            y: {
                beginAtZero: true
            }
        }
    }
});

function updateDailyStats() {
    fetch('/api/addresses-by-day')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            dailyChart.data.labels = data.map(item => item.date);  
            dailyChart.data.datasets[0].data = data.map(item => item.count); 
            dailyChart.update();
        })
        .catch(error => {
            console.log('There was a problem with the fetch operation:', error.message);
        });
}

const eventSource = new EventSource('/api/addresses-by-day');

eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    dailyChart.data.labels = data.map(item => item.date); 
    dailyChart.data.datasets[0].data = data.map(item => item.count);
    dailyChart.update();
};

function humanFormat(number) {
    let magnitude = 0;
    while (Math.abs(number) >= 1000) {
        magnitude += 1;
        number /= 1000.0;
    }
    return number.toFixed(4) + ' ' + ['', 'K', 'M', 'B', 'T'][magnitude];
}

function updateTotalAddresses() {
    fetch('/api/total-addresses')
        .then(response => response.json())
        .then(data => {
            document.querySelector('#totalAddresses').textContent = `Total addresses processed: ${humanFormat(data.total_addresses)}`;
        })
        .catch(error => {
            console.error('Error fetching total addresses:', error);
        });
}
setInterval(updateTotalAddresses, 5000);

function updateTotalAddressesInChart() {
    fetch('/api/total-addresses')
        .then(response => response.json())
        .then(data => {
            overallChart.data.datasets[0].data[1] = data.total_addresses; 
            overallChart.update(); 
        })
        .catch(error => {
            console.error('Error fetching total addresses:', error);
        });
}
setInterval(updateTotalAddressesInChart, 5000);
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
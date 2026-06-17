class F1ArchiveApp {
    constructor() {
        this.currentYear = null;
        this.currentRound = null;
        this.chartInstance = null;
        this.init();
    }

    init() {
        this.initChart();
        this.bindEvents();
    }

    initChart() {
        const ctx = document.getElementById('pitWindowChart').getContext('2d');
        
        // Define F1 Red gradient for the bar chart
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(225, 6, 0, 0.8)');   // F1 Red Solid
        gradient.addColorStop(1, 'rgba(225, 6, 0, 0.1)');   // F1 Red Transparent

        this.chartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [], // Lap numbers
                datasets: [{
                    label: 'Pit Stops',
                    data: [], // Frequency count
                    backgroundColor: gradient,
                    borderColor: '#e10600',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { 
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#888892', font: {family: 'monospace'} }
                    },
                    x: { 
                        grid: { display: false },
                        ticks: { color: '#888892', font: {family: 'monospace'}, maxTicksLimit: 20 }
                    }
                },
                plugins: { 
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#202029',
                        titleColor: '#ffffff',
                        bodyColor: '#e10600',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        displayColors: false,
                        callbacks: {
                            title: (items) => `Lap ${items[0].label}`,
                            label: (item) => `${item.raw} Cars Pitted`
                        }
                    }
                }
            }
        });
    }

    bindEvents() {
        // Year selection
        document.getElementById('yearSelect').addEventListener('change', (e) => {
            this.currentYear = e.target.value;
            this.resetDashboard();
            if (this.currentYear) this.loadEvents(this.currentYear);
        });
        
        // Event selection
        document.getElementById('eventSelect').addEventListener('change', (e) => {
            this.currentRound = e.target.value;
            document.getElementById('analyze-btn').disabled = false;
        });

        // Analyze Button
        document.getElementById('analyze-btn').addEventListener('click', () => {
            if (this.currentYear && this.currentRound) {
                this.fetchTrackStats();
            }
        });
    }

    resetDashboard() {
        const eventSelect = document.getElementById('eventSelect');
        eventSelect.innerHTML = '<option value="" disabled selected>Select Race</option>';
        eventSelect.disabled = true;
        document.getElementById('analyze-btn').disabled = true;
        this.currentRound = null;
        
        // Clear UI stats
        document.getElementById('stat-pit-time').textContent = '-- s';
        document.getElementById('stat-compound').textContent = '--';
        document.getElementById('stat-total-stops').textContent = '--';
        
        // Clear Chart
        this.chartInstance.data.labels = [];
        this.chartInstance.data.datasets[0].data = [];
        this.chartInstance.update();
    }

    async loadEvents(year) {
        try {
            const response = await fetch(`/api/events/${year}`);
            const data = await response.json();
            const eventSelect = document.getElementById('eventSelect');
            
            // Re-initialize clear default selection header
            eventSelect.innerHTML = '<option value="" disabled selected>Select Race</option>';
            
            if (data.events && data.events.length > 0) {
                data.events.forEach(event => {
                    const option = document.createElement('option');
                    // Ensure the value property is mapped directly to the numerical round identifier
                    option.value = event.RoundNumber; 
                    option.textContent = `${event.RoundNumber}. ${event.EventName}`;
                    eventSelect.appendChild(option);
                });
                eventSelect.disabled = false;
            }
        } catch (error) {
            console.error('Error loading events:', error);
        }
    }

    async fetchTrackStats() {
        const btn = document.getElementById('analyze-btn');
        const btnText = btn.querySelector('.btn-text');
        const btnLoader = btn.querySelector('.btn-loader');

        try {
            // UI Loading state
            btn.disabled = true;
            btnText.classList.add('hidden');
            btnLoader.classList.remove('hidden');

            const response = await fetch(`/api/track-stats/${this.currentYear}/${this.currentRound}`);
            
            // 1. Get raw text first to prevent JSON crash on HTML error pages
            const textResponse = await response.text();
            
            let data;
            try {
                // 2. Safely attempt to parse JSON
                data = JSON.parse(textResponse);
            } catch (parseError) {
                console.error("Failed to parse response as JSON. Server returned:", textResponse);
                alert("Server error: The backend returned an invalid response.");
                return;
            }

            // 3. Handle successful data payload
            if (data.success) {
                // Update Quick Stats
                document.getElementById('stat-pit-time').textContent = `${data.avg_pit_time.toFixed(2)} s`;
                document.getElementById('stat-compound').textContent = data.popular_compound;
                document.getElementById('stat-total-stops').textContent = data.total_stops;

                // Update Chart
                const laps = Object.keys(data.distribution).map(Number).sort((a, b) => a - b);
                const counts = laps.map(lap => data.distribution[lap]);

                this.chartInstance.data.labels = laps;
                this.chartInstance.data.datasets[0].data = counts;
                this.chartInstance.update();
            } else {
                // Display the safe error message from Python
                alert(`Data Alert: ${data.error}`);
            }

        } catch (error) {
            console.error("Failed to fetch track stats:", error);
            alert("Failed to connect to the backend API.");
        } finally {
            btn.disabled = false;
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new F1ArchiveApp();
});
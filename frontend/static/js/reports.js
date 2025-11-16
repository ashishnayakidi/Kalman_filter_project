// Reports functionality
document.addEventListener('DOMContentLoaded', function() {
    const generateBtn = document.getElementById('generate-btn');
    const reportContent = document.getElementById('report-content');

    generateBtn.addEventListener('click', async function() {
        this.disabled = true;
        this.textContent = 'Generating...';
        reportContent.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"></div><p class="mt-2">Generating report...</p></div>';

        try {
            const response = await fetch('/api/weekly_report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const data = await response.json();

            if (data.error) {
                reportContent.innerHTML = `<div class="alert alert-danger">Error: ${data.error}</div>`;
            } else {
                // Convert markdown-like formatting to HTML
                let report = data.report;
                report = report.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                report = report.replace(/\*(.*?)\*/g, '<em>$1</em>');
                report = report.replace(/^### (.*$)/gm, '<h5>$1</h5>');
                report = report.replace(/^## (.*$)/gm, '<h4>$1</h4>');
                report = report.replace(/^# (.*$)/gm, '<h3>$1</h3>');
                report = report.replace(/^- (.*$)/gm, '<li>$1</li>');
                report = report.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
                report = report.replace(/\n/g, '<br>');
                
                reportContent.innerHTML = `<div class="report-content">${report}</div>`;
            }
        } catch (error) {
            reportContent.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
        } finally {
            this.disabled = false;
            this.textContent = 'Generate Weekly Report';
        }
    });
});

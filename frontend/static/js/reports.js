// Reports functionality
let currentReport = null;

document.addEventListener('DOMContentLoaded', function() {
    const generateBtn = document.getElementById('generate-btn');
    const downloadBtn = document.getElementById('download-btn');
    const emailBtn = document.getElementById('email-btn');
    const emailForm = document.getElementById('email-form');
    const sendEmailBtn = document.getElementById('send-email-btn');
    const cancelEmailBtn = document.getElementById('cancel-email-btn');
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
                currentReport = data.report;
                
                // Convert markdown-like formatting to HTML
                let report = data.report;
                
                // Split into lines for better processing
                let lines = report.split('\n');
                let htmlLines = [];
                let inList = false;
                
                for (let i = 0; i < lines.length; i++) {
                    let originalLine = lines[i];
                    let line = originalLine.trim();
                    
                    // Skip empty lines (will add <br> later)
                    if (line === '') {
                        if (inList) {
                            htmlLines.push('</ul>');
                            inList = false;
                        }
                        htmlLines.push('');
                        continue;
                    }
                    
                    // Process headings first (most specific to least)
                    // Match headings that start with # (with any number of #, with or without space)
                    let headingMatch = line.match(/^(#{1,6})\s*(.+)$/);
                    if (headingMatch && line.startsWith('#')) {
                        if (inList) {
                            htmlLines.push('</ul>');
                            inList = false;
                        }
                        let hashCount = headingMatch[1].length;
                        let headingText = headingMatch[2].trim();
                        
                        // Remove any remaining # symbols from the heading text (in case of malformed markdown)
                        headingText = headingText.replace(/^#+\s*/, '');
                        
                        // Map # count to heading level
                        if (hashCount >= 3) {
                            htmlLines.push(`<h5>${headingText}</h5>`);
                        } else if (hashCount === 2) {
                            htmlLines.push(`<h4>${headingText}</h4>`);
                        } else {
                            htmlLines.push(`<h3>${headingText}</h3>`);
                        }
                    } else if (line.startsWith('- ') || line.startsWith('* ')) {
                        if (!inList) {
                            htmlLines.push('<ul>');
                            inList = true;
                        }
                        let item = line.substring(2).trim();
                        // Process bold and italic in list items
                        item = item.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                        item = item.replace(/\*(.*?)\*/g, '<em>$1</em>');
                        htmlLines.push(`<li>${item}</li>`);
                    } else {
                        // Regular paragraph text
                        if (inList) {
                            htmlLines.push('</ul>');
                            inList = false;
                        }
                        // Process bold and italic
                        line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                        line = line.replace(/\*(.*?)\*/g, '<em>$1</em>');
                        htmlLines.push(`<p>${line}</p>`);
                    }
                }
                
                // Close any open list
                if (inList) {
                    htmlLines.push('</ul>');
                }
                
                // Join lines with newlines (empty lines become <br>)
                report = htmlLines.map(line => line === '' ? '<br>' : line).join('\n');
                
                reportContent.innerHTML = `<div class="report-content">${report}</div>`;
                
                // Show download and email buttons
                downloadBtn.style.display = 'inline-block';
                emailBtn.style.display = 'inline-block';
            }
        } catch (error) {
            reportContent.innerHTML = `<div class="alert alert-danger">Error: ${error.message}</div>`;
        } finally {
            this.disabled = false;
            this.textContent = 'Generate Weekly Report';
        }
    });

    downloadBtn.addEventListener('click', function() {
        if (!currentReport) return;
        
        // Create downloadable text file
        const blob = new Blob([currentReport], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `battery-health-report-${new Date().toISOString().split('T')[0]}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    emailBtn.addEventListener('click', function() {
        if (emailForm.style.display === 'none' || emailForm.style.display === '') {
            emailForm.style.display = 'block';
            // Focus on email input when form is shown
            setTimeout(() => {
                const emailInput = document.getElementById('email-input');
                if (emailInput) {
                    emailInput.focus();
                    emailInput.disabled = false;
                }
                const subjectInput = document.getElementById('email-subject');
                if (subjectInput) {
                    subjectInput.disabled = false;
                }
            }, 100);
        } else {
            emailForm.style.display = 'none';
        }
    });

    cancelEmailBtn.addEventListener('click', function() {
        emailForm.style.display = 'none';
    });

    sendEmailBtn.addEventListener('click', async function() {
        const email = document.getElementById('email-input').value;
        const subject = document.getElementById('email-subject').value || 'Weekly Battery Health Report';
        
        if (!email) {
            alert('Please enter an email address');
            return;
        }

        this.disabled = true;
        this.textContent = 'Sending...';

        try {
            const response = await fetch('/api/send_report_email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: email,
                    subject: subject,
                    report: currentReport
                })
            });

            const data = await response.json();

            if (data.error) {
                // Show detailed error message
                let errorMsg = data.error;
                if (data.message) {
                    errorMsg += '\n\n' + data.message;
                }
                if (data.instructions && Array.isArray(data.instructions)) {
                    errorMsg += '\n\nConfiguration needed:\n' + data.instructions.join('\n');
                }
                if (data.note) {
                    errorMsg += '\n\nNote: ' + data.note;
                }
                alert(errorMsg);
            } else {
                alert('Report sent successfully!');
                emailForm.style.display = 'none';
                document.getElementById('email-input').value = '';
                document.getElementById('email-subject').value = '';
            }
        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            this.disabled = false;
            this.textContent = 'Send Email';
        }
    });
});

"""
Report generation: JSON and HTML formats.
"""

from jinja2 import Template


class ReportGenerator:
    """Generates verification reports in multiple formats."""

    @staticmethod
    def generate_json_report(project_id: str) -> dict:
        """
        Generate a comprehensive JSON report.

        Args:
            project_id: ID of the project

        Returns:
            Dict with full report data
        """
        from backend.services.verification import load_report
        return load_report(project_id)

    @staticmethod
    def generate_html_report(project_id: str) -> str:
        """
        Generate an HTML report.

        Args:
            project_id: ID of the project

        Returns:
            HTML string
        """
        report_data = ReportGenerator.generate_json_report(project_id)

        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SpecGuard Verification Report - {{ project_id }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            font-size: 1.4em;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card.passed { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
        .stat-card.failed { background: linear-gradient(135deg, #ee0979 0%, #ff6a00 100%); }
        .stat-card.flaky { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .stat-card.error { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }
        .stat-card h3 { font-size: 2em; margin-bottom: 5px; }
        .stat-card p { font-size: 0.9em; opacity: 0.9; }
        .requirement {
            background: #f9f9f9;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }
        .test-result {
            margin: 10px 0;
            padding: 10px;
            background: #f0f0f0;
            border-radius: 4px;
            border-left: 3px solid #bbb;
        }
        .test-result.passed { border-left-color: #27ae60; background: #ecf0f1; }
        .test-result.failed { border-left-color: #e74c3c; background: #fadbd8; }
        .test-result.flaky { border-left-color: #f39c12; background: #fef5e7; }
        .status-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .status-badge.passed { background: #d4edda; color: #155724; }
        .status-badge.failed { background: #f8d7da; color: #721c24; }
        .status-badge.flaky { background: #fff3cd; color: #856404; }
        .status-badge.error { background: #f5c6cb; color: #721c24; }
        .output {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            max-height: 300px;
            overflow-y: auto;
        }
        .finding {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .suggestion {
            background: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .code-block {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 10px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-x: auto;
            max-height: 300px;
            overflow-y: auto;
        }
        .generated-at {
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>SpecGuard Verification Report</h1>
        <p><strong>Project ID:</strong> {{ project_id }}</p>

        <h2>Summary</h2>
        <div class="summary">
            <div class="stat-card">
                <h3>{{ summary.total_requirements }}</h3>
                <p>Requirements</p>
            </div>
            <div class="stat-card">
                <h3>{{ summary.total_tests }}</h3>
                <p>Tests Generated</p>
            </div>
            <div class="stat-card passed">
                <h3>{{ summary.passed }}</h3>
                <p>Passed</p>
            </div>
            <div class="stat-card failed">
                <h3>{{ summary.failed }}</h3>
                <p>Failed</p>
            </div>
            <div class="stat-card flaky">
                <h3>{{ summary.flaky }}</h3>
                <p>Flaky</p>
            </div>
        </div>

        <h2>Requirements & Test Results</h2>
        {% for requirement in requirements %}
        <div class="requirement">
            <h3>{{ requirement.text }}</h3>
            <p><strong>Category:</strong> {{ requirement.category }}</p>
            <p><strong>Measurable Criteria:</strong> {{ requirement.measurable_criteria }}</p>
            {% if requirement.ambiguous %}
            <p><strong>Note:</strong> {{ requirement.clarification_note }}</p>
            {% endif %}

            <h4>Test Results</h4>
            {% set req_results = test_results | selectattr('requirement_id', 'equalto', requirement.id) | list %}
            {% if req_results %}
                {% for result in req_results %}
                <div class="test-result {{ result.status }}">
                    <strong>Test {{ result.test_id }}:</strong>
                    <span class="status-badge {{ result.status }}">{{ result.status | upper }}</span>
                    <p style="margin-top: 5px;"><strong>Duration:</strong> {{ result.duration_ms }}ms</p>
                    {% if result.output %}
                    <details>
                        <summary>Output</summary>
                        <div class="output">{{ result.output }}</div>
                    </details>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
            <p><em>No test results for this requirement yet.</em></p>
            {% endif %}
        </div>
        {% endfor %}

        {% if static_findings %}
        <h2>Static Analysis Findings</h2>
        {% for finding in static_findings %}
        <div class="finding">
            <strong>Line {{ finding.line }}:</strong> {{ finding.message }}
        </div>
        {% endfor %}
        {% endif %}

        {% if fix_suggestions %}
        <h2>Fix Suggestions</h2>
        {% for suggestion in fix_suggestions %}
        <div class="suggestion">
            <h4>For Requirement {{ suggestion.requirement_id }}</h4>
            <p><strong>Explanation:</strong> {{ suggestion.explanation }}</p>
            <p><strong>Suggested Code:</strong></p>
            <div class="code-block">{{ suggestion.patched_code }}</div>
        </div>
        {% endfor %}
        {% endif %}

        <div class="generated-at">
            <p>Report generated at: {{ generated_at }}</p>
        </div>
    </div>
</body>
</html>
"""
        template = Template(template_str, autoescape=True)
        html = template.render(
            project_id=project_id,
            summary=report_data["summary"],
            requirements=report_data["requirements"],
            test_results=report_data["test_results"],
            static_findings=report_data["static_findings"],
            fix_suggestions=report_data["fix_suggestions"],
            generated_at=report_data["generated_at"],
        )
        return html

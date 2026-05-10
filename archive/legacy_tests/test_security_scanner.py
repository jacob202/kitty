from src.utils.security_scanner import SecurityFinding, SecurityReport, scan_files, scan_text


def rules(findings):
    return {finding.rule for finding in findings}


def test_detects_hardcoded_openrouter_key_assignment():
    findings = scan_text("settings.py", 'OPENROUTER_API_KEY = "sk-live-secret-value-1234567890"')

    assert "hardcoded_secret" in rules(findings)
    finding = findings[0]
    assert finding.path == "settings.py"
    assert finding.severity == "critical"
    assert finding.line == 1


def test_ignores_placeholder_key_examples():
    findings = scan_text(
        ".env.example",
        'OPENROUTER_API_KEY="sk-or-..."\nANTHROPIC_API_KEY="your-key-here"',
    )

    assert findings == []


def test_detects_private_key_block():
    findings = scan_text("id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----")

    assert "private_key" in rules(findings)


def test_detects_generic_api_key_literal():
    findings = scan_text("notes.txt", "token = sk-1234567890abcdefghijklmnop")

    assert "api_key_literal" in rules(findings)


def test_detects_dangerous_execution_patterns():
    content = "\n".join(
        [
            "subprocess.run('echo hi', shell=True)",
            "os.system('rm -rf /tmp/x')",
            "eval(user_input)",
            "exec(code)",
        ]
    )

    found = rules(scan_text("builder.py", content))

    assert "subprocess_shell_true" in found
    assert "os_system" in found
    assert "eval" in found
    assert "exec" in found
    assert "rm_rf" in found


def test_detects_chmod_and_path_traversal():
    found = rules(scan_text("script.sh", "chmod 777 file\nopen('../secret.txt')"))

    assert "chmod_777" in found
    assert "path_traversal" in found


def test_scan_files_returns_report():
    report = scan_files(
        {
            "safe.py": "print('ok')",
            "bad.py": "PASSWORD = 'real-password-value'",
        }
    )

    assert isinstance(report, SecurityReport)
    assert not report.ok
    assert report.count == 1
    assert report.by_severity("critical")[0].path == "bad.py"


def test_finding_is_structured():
    finding = scan_text("bad.py", "eval(x)")[0]

    assert isinstance(finding, SecurityFinding)
    assert finding.rule == "eval"
    assert finding.message
    assert finding.excerpt == "eval(x)"

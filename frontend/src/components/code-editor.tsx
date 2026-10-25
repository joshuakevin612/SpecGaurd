import { useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { Check, Clipboard, Upload, Code2 } from 'lucide-react';

export function CodeEditor({
  value,
  onChange,
  disabled = false,
  placeholder = '# Paste Python source code here...',
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [copied, setCopied] = useState(false);
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState('');

  const lines = Math.max(1, value.split('\n').length);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = textareaRef.current;
      if (!textarea) return;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const nextValue = value.substring(0, start) + '    ' + value.substring(end);
      onChange(nextValue);
      window.requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 4;
      });
    }
  };

  const readFile = (file?: File) => {
    if (!file) return;
    if (file.size > 60000) { setFileError('Python files must be 60 KB or smaller.'); return; }
    setFileError('');
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') onChange(reader.result);
    };
    reader.readAsText(file);
  };

  return (
    <div className="code-editor-shell">
      <div className="editor-header-bar">
        <div className="editor-title-group">
          <span
            className="mono"
            style={{
              padding: '2px 7px',
              borderRadius: 'var(--r-xs)',
              background: 'var(--surface-card)',
              border: '1px solid var(--line)',
              color: 'var(--accent)',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            PY
          </span>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--ink)' }}>
            {fileName || 'main.py'}
          </span>
        </div>

        <div className="editor-actions-group">
          <label
            className="btn btn-ghost btn-sm"
            style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
            title="Upload Python file"
          >
            <Upload size={14} />
            <span>Upload</span>
            <input
              type="file"
              accept=".py,text/x-python,text/plain"
              style={{ display: 'none' }}
              disabled={disabled}
              onChange={(e) => readFile(e.target.files?.[0])}
            />
          </label>

          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={copyCode}
            disabled={!value || disabled}
            title={copied ? 'Code copied' : 'Copy code to clipboard'}
          >
            {copied ? <Check size={14} style={{ color: 'var(--status-pass)' }} /> : <Clipboard size={14} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      <div className="code-area-container">
        <div className="line-numbers-col" aria-hidden="true">
          {Array.from({ length: lines }, (_, idx) => (
            <div key={idx} style={{ height: '24px' }}>
              {idx + 1}
            </div>
          ))}
        </div>

        <textarea
          ref={textareaRef}
          className="code-textarea"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          placeholder={placeholder}
          aria-label="Python source code"
          style={{ minHeight: '340px' }}
        />
      </div>

      {fileError && <p role="alert" className="editor-file-error">{fileError}</p>}
      <div className="editor-statusbar">
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <Code2 size={13} style={{ color: 'var(--accent)' }} />
          <span>Python 3.11 · Function test inputs</span>
        </span>
        <span className="mono">{lines} lines · {value.length} bytes</span>
      </div>
    </div>
  );
}

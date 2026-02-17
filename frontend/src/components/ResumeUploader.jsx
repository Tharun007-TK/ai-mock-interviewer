/**
 * ResumeUploader — Drag-and-drop PDF upload component with file validation.
 */

import { useState, useRef } from 'react';

export default function ResumeUploader({ onUpload, isLoading }) {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const inputRef = useRef(null);

  function handleFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      alert('Please upload a PDF file.');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      alert('File size must be under 5MB.');
      return;
    }
    setFileName(file.name);
    onUpload(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setDragActive(true);
  }

  function handleDragLeave() {
    setDragActive(false);
  }

  function handleClick() {
    inputRef.current?.click();
  }

  function handleInputChange(e) {
    const file = e.target.files[0];
    handleFile(file);
  }

  return (
    <div
      onClick={handleClick}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`
        relative cursor-pointer rounded-2xl border-2 border-dashed p-10
        transition-all duration-300 text-center
        ${dragActive
          ? 'border-primary bg-primary/10 scale-[1.02]'
          : 'border-text-muted/30 hover:border-primary/50 hover:bg-surface-light/50'
        }
        ${isLoading ? 'pointer-events-none opacity-60' : ''}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={handleInputChange}
        disabled={isLoading}
      />

      {/* Icon */}
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
        <svg className="h-8 w-8 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12-3-3m0 0-3 3m3-3v6m-1.5-15H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
        </svg>
      </div>

      {isLoading ? (
        <div>
          <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-text-muted">Parsing resume...</p>
        </div>
      ) : fileName ? (
        <div>
          <p className="text-sm font-medium text-success">✓ {fileName}</p>
          <p className="mt-1 text-xs text-text-muted">Click to replace</p>
        </div>
      ) : (
        <div>
          <p className="text-sm font-medium text-text">
            Drop your resume here or <span className="text-primary">browse</span>
          </p>
          <p className="mt-1 text-xs text-text-muted">PDF only · Max 5MB</p>
        </div>
      )}
    </div>
  );
}

import React, { useRef, useState, useEffect } from 'react';
import { UploadCloud, FileText, AlertTriangle } from 'lucide-react';
import { MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from '../../lib/constants';

interface DropzoneProps {
  onFileSelected: (file: File) => void;
  isProcessing: boolean;
  statusText?: string;
}

export const Dropzone: React.FC<DropzoneProps> = ({
  onFileSelected,
  isProcessing,
  statusText = 'Sending your file and checking its contents…',
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (isProcessing) {
      setElapsed(0);
      interval = setInterval(() => {
        setElapsed((prev) => prev + 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isProcessing]);

  const validateAndHandle = (file: File) => {
    setValidationError(null);

    // Extension check
    const lowerName = file.name.toLowerCase();
    const isSupported = lowerName.endsWith('.csv') || lowerName.endsWith('.xlsx');
    if (!isSupported) {
      setValidationError('Choose a .csv or .xlsx file.');
      return;
    }

    // Size check
    if (file.size > MAX_UPLOAD_BYTES) {
      setValidationError(`File size exceeds ${MAX_UPLOAD_MB} MB limit (${(file.size / 1_000_000).toFixed(1)} MB).`);
      return;
    }

    if (file.size === 0) {
      setValidationError('The selected file is empty (0 bytes).');
      return;
    }

    onFileSelected(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (isProcessing) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndHandle(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!isProcessing) setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  return (
    <div className="space-y-3">
      <div
        role="button"
        tabIndex={isProcessing ? -1 : 0}
        aria-label="Choose a CSV or Excel file to analyze"
        aria-disabled={isProcessing}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        onKeyDown={(event) => { if (!isProcessing && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); fileInputRef.current?.click(); } }}
        className={`relative border-2 border-dashed rounded-2xl p-10 text-center transition-all cursor-pointer select-none ${
          isProcessing
            ? 'bg-slate-50 border-slate-300 cursor-wait'
            : isDragOver
            ? 'bg-emerald-50/60 border-emerald-500 scale-[1.005]'
            : 'bg-white hover:bg-slate-50/80 border-slate-300 hover:border-slate-400'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="hidden"
          disabled={isProcessing}
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              validateAndHandle(e.target.files[0]);
            }
            e.currentTarget.value = '';
          }}
        />

        {isProcessing ? (
          <div className="space-y-4 py-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center animate-pulse">
              <FileText className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-800">{statusText}</div>
              <p className="text-xs text-slate-500 font-mono">
                Progress is not available for this request · {elapsed}s elapsed
              </p>
            </div>
            <div className="w-48 h-1.5 mx-auto bg-slate-200 rounded-full overflow-hidden">
              <div className="w-full h-full bg-emerald-500 animate-[pulse_1.5s_infinite]" />
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="w-12 h-12 mx-auto rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center">
              <UploadCloud className="w-6 h-6 text-slate-700" />
            </div>
            <div>
              <div className="text-base font-semibold text-slate-800">
                {isDragOver ? 'Release to upload' : 'Drop a CSV or XLSX here, or browse'}
              </div>
              <p className="text-xs text-slate-500 mt-1">
                CSV and XLSX · Max {MAX_UPLOAD_MB} MB · Select a worksheet after choosing a workbook
              </p>
            </div>
          </div>
        )}
      </div>

      {validationError && (
        <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded-xl text-xs flex items-center gap-2.5">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
};

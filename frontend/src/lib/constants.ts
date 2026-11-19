/**
 * DataFix Application Constants
 * Aligned with backend settings and docs/FRONTEND_DESIGN_SPEC.md
 */

// Keep browser validation aligned with FastAPI's 5 MiB default.
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MAX_UPLOAD_MB = 5;

export const SUPPORTED_EXTENSIONS = ['.csv'];
export const SUPPORTED_MIME_TYPES = ['text/csv', 'application/vnd.ms-excel'];

export const SAMPLE_DATASET_NAME = 'customers_demo.csv';
export const SAMPLE_DATASET_PATH = '/sample_data/customers_demo.csv';

export const APP_NAME = 'DataFix';
export const APP_TAGLINE = 'TRUST-FIRST STRUCTURED DATA QUALITY';
export const VERSION = '0.1.0';

export const NAVIGATION_STAGES = [
  { id: 'intake', label: 'Intake', step: '①' },
  { id: 'overview', label: 'Overview', step: '②' },
  { id: 'studio', label: 'Studio', step: '③' },
  { id: 'proof', label: 'Proof', step: '④' },
] as const;

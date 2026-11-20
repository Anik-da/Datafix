/**
 * WalkthroughPage.tsx — Full Cinematic DataFix Walkthrough Experience.
 *
 * Dedicated route view rendered at `#/walkthrough`.
 * Renders outside the visual AppShell chrome (TopBar, SafetyRibbon, StageRail),
 * while retaining all root application providers (RouterContext, RunContext, SystemContext).
 *
 * Completely scoped inside `.df-walkthrough` container to prevent any CSS leaks.
 */

import React, { useCallback, useState } from 'react';
import { uploadAndAnalyze } from '../lib/api';
import { useRouter } from '../app/routes';
import { useRun } from '../app/context/RunContext';
import { VisualStoryExperience } from '../components/story/VisualStoryExperience';
import { sampleStoryAdapter } from '../components/story/adapters/sampleStoryAdapter';
import '../styles/walkthrough.css';

export const WalkthroughPage: React.FC = () => {
  const { navigate } = useRouter();
  const { currentRun, loadAnalysisAsRun } = useRun();
  const [isStartingLiveDemo, setIsStartingLiveDemo] = useState(false);
  const [liveDemoStage, setLiveDemoStage] = useState<'loading' | 'uploading' | 'analyzing' | null>(null);
  const [liveDemoError, setLiveDemoError] = useState<string | null>(null);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('datafix_theme') as 'light' | 'dark' | null;
      if (stored) return stored;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return 'light';
  });

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'light' ? 'dark' : 'light';
      if (typeof window !== 'undefined') {
        localStorage.setItem('datafix_theme', next);
      }
      return next;
    });
  }, []);

  const handleStartLiveDemo = useCallback(async () => {
    if (isStartingLiveDemo) return;
    setIsStartingLiveDemo(true);
    setLiveDemoStage('loading');
    setLiveDemoError(null);
    try {
      const response = await fetch('/demo/walkthrough_dirty.csv');
      if (!response.ok) throw new Error('The synthetic walkthrough CSV could not be loaded.');
      const file = new File([await response.blob()], 'walkthrough_dirty.csv', { type: 'text/csv' });
      const run = await uploadAndAnalyze(file, undefined, (stage) => setLiveDemoStage(stage));
      const runId = loadAnalysisAsRun(run);
      navigate(`/runs/${runId}/overview`);
    } catch (error) {
      setLiveDemoError(error instanceof Error ? error.message : 'The live sample could not be analyzed. Check that the backend is running.');
    } finally {
      setIsStartingLiveDemo(false);
      setLiveDemoStage(null);
    }
  }, [isStartingLiveDemo, loadAnalysisAsRun, navigate]);

  const handleExit = useCallback(() => {
    if (currentRun?.run_id) {
      navigate(`/runs/${currentRun.run_id}/overview`);
    } else {
      navigate('/app');
    }
  }, [currentRun, navigate]);

  const handleScrollToDemo = useCallback(() => {
    const demoEl = document.querySelector('.v3-cinematic-section');
    if (demoEl) {
      demoEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const handleScrollToTop = useCallback(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  return (
    <div
      className="df-walkthrough"
      data-theme={theme}
      data-testid="walkthrough-container"
    >
      {/* ------------------------------------------------------------------
          1. Introduction Section — Soda-Style Fresh Mint Hero (Desktop-first)
          ------------------------------------------------------------------ */}
      <header className="df-poc-intro">
        {/* Top Navigation Bar */}
        <nav className="df-intro-nav" aria-label="DataFix product demonstration navigation">
          <div className="df-intro-brand">
            <span className="df-brand-logo-mark" aria-hidden="true">DF</span>
            <span className="df-brand-name">DATAFIX</span>
            <span className="df-brand-sep" aria-hidden="true">/</span>
            <span className="df-brand-label">Product Walkthrough</span>
          </div>

          <div className="df-intro-nav-actions">
            {/* Exit to workspace button */}
            <button
              type="button"
              className="df-theme-toggle"
              onClick={handleExit}
              title={currentRun?.run_id ? "Return to operational run" : "Launch DataFix application"}
              data-testid="hero-exit-button"
              style={{
                fontWeight: 600,
                color: 'var(--df-emerald-text)',
                borderColor: 'var(--df-emerald-border)',
                background: 'var(--df-emerald-50)',
              }}
            >
              <span>{currentRun?.run_id ? '← Return to Run' : 'Launch App →'}</span>
            </button>

            {/* Light / Dark Mode Toggle */}
            <button
              type="button"
              className="df-theme-toggle"
              onClick={handleToggleTheme}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              data-testid="hero-theme-toggle"
            >
              {theme === 'dark' ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="5" />
                    <line x1="12" y1="1" x2="12" y2="3" />
                    <line x1="12" y1="21" x2="12" y2="23" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="1" y1="12" x2="3" y2="12" />
                    <line x1="21" y1="12" x2="23" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                  </svg>
                  <span>Light Mode</span>
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                  </svg>
                  <span>Dark Mode</span>
                </>
              )}
            </button>

            <div className="df-nav-pill">
              <span className="df-nav-status-dot" aria-hidden="true" />
              Illustrative story · Live analysis available
            </div>
          </div>
        </nav>

        {/* Hero Content — Centred Headline & Value Prop */}
        <div className="df-intro-content">
          <div className="df-intro-eyebrow">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
            Data Quality &amp; Verifiable Repair
          </div>

          <h1 className="df-poc-title">
            Fix dirty data.{' '}
            <span className="df-title-em">Prove every change.</span>
          </h1>

          <p className="df-poc-subtitle">
            Upload a CSV or workbook to see a measured profile, evidence-backed findings,
            typed repair suggestions, safety decisions, verification, and downloadable run records.
            Try the live synthetic sample to see results from the configured backend.
          </p>

          <div className="df-hero-actions">
            <button
              type="button"
              className="df-hero-cta-primary"
              onClick={handleScrollToDemo}
              aria-label="Scroll down to view the illustrative 8-stage walkthrough"
              data-testid="hero-explore-cta"
            >
              <span>Explore the Illustrative Pipeline</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="12" y1="5" x2="12" y2="19" />
                <polyline points="19 12 12 19 5 12" />
              </svg>
            </button>
            <button
              type="button"
              className="df-hero-cta-secondary"
              onClick={handleStartLiveDemo}
              disabled={isStartingLiveDemo}
              aria-label="Upload the synthetic sample to the live backend and analyze it"
              data-testid="live-sample-analysis-cta"
            >
              {isStartingLiveDemo
                ? liveDemoStage === 'loading' ? 'Loading sample…' : liveDemoStage === 'uploading' ? 'Uploading sample…' : 'Analyzing dataset…'
                : 'Run Live Sample Analysis'}
            </button>
            <button
              type="button"
              className="df-hero-cta-secondary"
              onClick={handleExit}
              aria-label="Launch DataFix workspace"
              data-testid="hero-launch-app-cta"
            >
              Launch App →
            </button>
          </div>
          {(liveDemoError || liveDemoStage) && <p className="df-live-demo-status" role={liveDemoError ? 'alert' : 'status'} aria-live="polite" data-testid="live-demo-status">
            {liveDemoError || (liveDemoStage === 'loading' ? 'Preparing the real sample dataset…'
              : liveDemoStage === 'uploading' ? 'Sample loaded. Uploading it to the DataFix backend…'
                : liveDemoStage === 'analyzing' ? 'Upload complete. The backend is profiling the data and checking repair safety. This can take a little while on a sleeping service…'
                  : '')}
          </p>}
        </div>

        {/* Hero App Mockup Preview */}
        <div className="df-hero-preview" aria-hidden="true">
          <div className="df-hero-preview-inner">
            <div className="df-preview-topbar">
              <div className="df-preview-window-controls" aria-hidden="true">
                <span className="df-pwin-dot is-red" />
                <span className="df-pwin-dot is-yellow" />
                <span className="df-pwin-dot is-green" />
              </div>
              <div className="df-preview-brand-wrapper">
                <span className="df-preview-logo">DataFix</span>
                <span className="df-preview-app-badge">Studio</span>
              </div>
              <div className="df-preview-nav-items">
                <span className="df-preview-nav-item is-active">
                  <span className="df-pnav-dot" />
                  Dashboards
                </span>
                <span className="df-preview-nav-item">Checks</span>
                <span className="df-preview-nav-item">Datasets</span>
                <span className="df-preview-nav-item">Findings</span>
                <span className="df-preview-nav-item">Runs</span>
              </div>
              <div className="df-preview-status-pill">
                <span className="df-pstatus-pulse" />
                <span>Illustrative preview</span>
              </div>
            </div>

            <div className="df-preview-body">
              <div className="df-preview-stat">
                <div className="df-pstat-header">
                  <span className="df-pstat-icon">🗄️</span>
                  <span className="df-preview-stat-label">Sample rows (illustrative)</span>
                </div>
                <div className="df-preview-stat-value">—</div>
                <div className="df-pstat-footer">
                  <span className="df-preview-stat-badge is-pass">Illustration</span>
                  <span className="df-pstat-ctx">Not a live upload</span>
                </div>
              </div>

              <div className="df-preview-stat is-warning-card">
                <div className="df-pstat-header">
                  <span className="df-pstat-icon">⚠️</span>
                  <span className="df-preview-stat-label">Issues detected (live)</span>
                </div>
                <div className="df-preview-stat-value">—</div>
                <div className="df-pstat-footer">
                  <span className="df-preview-stat-badge is-review">Run sample to see</span>
                  <span className="df-pstat-ctx">Counts come from the backend response</span>
                </div>
              </div>

              <div className="df-preview-stat is-score-card">
                <div className="df-pstat-header">
                  <span className="df-pstat-icon">🎯</span>
                  <span className="df-preview-stat-label">Quality score</span>
                </div>
                <div className="df-preview-stat-value">Not calculated</div>
                <div className="df-pstat-footer">
                  <span className="df-preview-stat-badge is-pass">No live run yet</span>
                  <div className="df-pscore-track" aria-hidden="true">

                  </div>
                </div>
              </div>
            </div>

            <div className="df-preview-caption">
              <div className="df-pcaption-left">
                <span className="df-pcaption-chip">ILLUSTRATIVE ONLY</span>
                <span>No dataset has been analyzed in this preview</span>
              </div>
              <div className="df-pcaption-right">
                <span className="df-pcaption-shield">Run the sample for actual backend results</span>
              </div>
            </div>
          </div>
        </div>

        {/* Scroll Cue */}
        <div
          className="df-scroll-cue"
          onClick={handleScrollToDemo}
          role="button"
          tabIndex={0}
          aria-label="Scroll to explore the 8 stages"
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleScrollToDemo(); }}
        >
          <span className="df-scroll-cue-line" aria-hidden="true" />
          <span className="df-scroll-cue-text">Scroll to explore stages</span>
        </div>
      </header>

      {/* ------------------------------------------------------------------
          2. Section Divider
          ------------------------------------------------------------------ */}
      <div className="df-section-label" aria-hidden="true">
        <span className="df-section-label-line" />
        <span className="df-section-label-text">How DataFix Works</span>
        <span className="df-section-label-line" />
      </div>

      {/* ------------------------------------------------------------------
          3. Main 8-Stage Cinematic Scroll Experience
          ------------------------------------------------------------------ */}
      <main>
        <div className="df-section-label-text" role="note">The animated story below is illustrative; it does not represent a completed run. Run the synthetic sample above to see real API results.</div>
        <VisualStoryExperience
          adapter={sampleStoryAdapter}
          onStartLiveDemo={handleStartLiveDemo}
          isStartingLiveDemo={isStartingLiveDemo}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          onExit={handleExit}
        />
      </main>

      {/* ------------------------------------------------------------------
          4. Outro Section — Journey Completion & Return Action
          ------------------------------------------------------------------ */}
      <footer className="df-poc-outro">
        <div className="df-outro-inner">
          <span className="df-outro-eyebrow">
            <span className="df-outro-check" aria-hidden="true">✓</span>
            Illustrative Preview Complete
          </span>

          <h2 className="df-outro-title">
            Fix the data. Prove every change.
          </h2>

          <p className="df-outro-subtitle">
            Use the live workspace to review measured findings, supported repair proposals,
            safety decisions, verification, and the operation history for your uploaded run.
            Unsupported or ambiguous corrections remain unresolved.
          </p>

          {/* Journey Strip — 8 emerald milestone circles */}
          <div className="df-journey-strip" aria-label="8-stage DataFix pipeline journey" role="list">
            {[
              { n: 1, label: 'Ingest' },
              { n: 2, label: 'Detect' },
              { n: 3, label: 'Diagnose' },
              { n: 4, label: 'Propose' },
              { n: 5, label: 'Simulate' },
              { n: 6, label: 'Gate & Apply' },
              { n: 7, label: 'Verify' },
              { n: 8, label: 'Proof' },
            ].map((stage, index) => (
              <div key={stage.n} className="df-journey-stage" role="listitem">
                {index > 0 && <span className="df-journey-connector" aria-hidden="true" />}
                <div className="df-journey-node">
                  <span className="df-journey-circle">{stage.n}</span>
                  <span className="df-journey-stage-label">{stage.label}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="df-outro-actions" style={{ display: 'flex', gap: '16px', justifyContent: 'center' }}>
            <button
              type="button"
              className="df-btn df-btn-approve"
              onClick={handleScrollToTop}
              aria-label="Restart demonstration and return to top"
              data-testid="outro-restart-btn"
            >
              <span>Restart Illustrative Preview</span>
              <span aria-hidden="true">↑</span>
            </button>
            <button
              type="button"
              className="df-btn"
              onClick={handleExit}
              aria-label="Launch DataFix workspace"
              data-testid="outro-return-app-btn"
              style={{
                background: 'var(--df-surface-white)',
                color: 'var(--df-text-heading)',
                border: '1px solid var(--df-surface-border-strong)',
                fontWeight: 600,
              }}
            >
              <span>Launch Workspace →</span>
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
};

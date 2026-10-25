import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { FileText, Cpu, FlaskConical, ShieldCheck, CheckCircle2, ArrowRight } from 'lucide-react';

export type PipelineStage = 'ingestion' | 'synthesis' | 'execution' | 'evidence';

type Props = {
  activeStage?: PipelineStage;
  onSelectStage?: (stage: PipelineStage) => void;
  isRunning?: boolean;
};

const STAGES: Array<{
  id: PipelineStage;
  num: string;
  title: string;
  shortDesc: string;
  icon: typeof FileText;
}> = [
  {
    id: 'ingestion',
    num: '01',
    title: 'Spec Parsing',
    shortDesc: 'Extracts atomic requirements & identifies ambiguities',
    icon: FileText,
  },
  {
    id: 'synthesis',
    num: '02',
    title: 'Case Synthesis',
    shortDesc: 'Generates behavioral cases tied to requirement IDs',
    icon: Cpu,
  },
  {
    id: 'execution',
    num: '03',
    title: 'Sandboxed Run',
    shortDesc: 'Runs function inputs with external comparisons and timeouts',
    icon: FlaskConical,
  },
  {
    id: 'evidence',
    num: '04',
    title: 'Evidence & Patches',
    shortDesc: 'Produces traceability matrix & synthesized code diffs',
    icon: ShieldCheck,
  },
];

export function VerificationPipelineStepper({
  activeStage = 'ingestion',
  onSelectStage,
  isRunning = false,
}: Props) {
  const [hoveredStage, setHoveredStage] = useState<PipelineStage | null>(null);
  const reduceMotion = useReducedMotion() ?? false;

  const currentIdx = STAGES.findIndex((s) => s.id === activeStage);

  return (
    <div className="pipeline-stepper-wrap" aria-label="Verification execution pipeline">
      <div className="pipeline-stepper-head">
        <div>
          <h2 style={{ fontSize: '1.35rem', marginTop: '2px' }}>Automated Verification Pipeline</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            className="mono"
            style={{
              fontSize: 'var(--text-xs)',
              padding: '4px 10px',
              borderRadius: 'var(--r-full)',
              background: isRunning ? 'var(--status-warn-bg)' : 'var(--surface-card)',
              border: `1px solid ${isRunning ? 'var(--status-warn-border)' : 'var(--line)'}`,
              color: isRunning ? 'var(--status-warn)' : 'var(--muted)',
            }}
          >
            {isRunning ? 'EXECUTION IN PROGRESS' : 'READY FOR VERIFICATION'}
          </span>
        </div>
      </div>

      <div className="pipeline-steps-track">
        {STAGES.map((stage, idx) => {
          const Icon = stage.icon;
          const isCurrent = stage.id === activeStage;
          const isPast = idx < currentIdx;

          return (
            <div
              key={stage.id}
              className={`pipeline-step ${isCurrent ? 'active' : ''} ${isPast ? 'completed' : ''}`}
              onClick={() => onSelectStage?.(stage.id)}
              onMouseEnter={() => setHoveredStage(stage.id)}
              onMouseLeave={() => setHoveredStage(null)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectStage?.(stage.id);
                }
              }}
            >
              <div className="step-topline">
                <div className="step-num-badge">
                  {isPast ? <CheckCircle2 size={13} /> : stage.num}
                </div>
                <Icon
                  size={16}
                  style={{
                    color: isCurrent ? 'var(--accent)' : isPast ? 'var(--status-pass)' : 'var(--muted)',
                  }}
                />
              </div>

              <div>
                <div className="step-title">{stage.title}</div>
                <div className="step-desc">{stage.shortDesc}</div>
              </div>

              {isCurrent && !reduceMotion && (
                <motion.div
                  layoutId="step-indicator"
                  style={{
                    position: 'absolute',
                    bottom: -1,
                    left: 12,
                    right: 12,
                    height: 2,
                    background: 'var(--accent)',
                    borderRadius: 2,
                  }}
                  transition={{ type: 'tween', duration: .42, ease: [.16, 1, .3, 1] }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

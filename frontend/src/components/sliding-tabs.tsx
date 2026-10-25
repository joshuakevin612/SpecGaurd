import { motion, useReducedMotion } from 'framer-motion';
import { type ReactNode } from 'react';

export type TabItem<T extends string> = {
  id: T;
  label: string;
  badge?: string | number;
  icon?: ReactNode;
};

type Props<T extends string> = {
  tabs: TabItem<T>[];
  activeTab: T;
  onChange: (id: T) => void;
  ariaLabel?: string;
};

export function SlidingTabs<T extends string>({
  tabs,
  activeTab,
  onChange,
  ariaLabel = 'Navigation tabs',
}: Props<T>) {
  const reduceMotion = useReducedMotion() ?? false;

  return (
    <div className="tabs-navigation-wrap" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            className={`tab-btn ${isActive ? 'active' : ''}`}
            onClick={() => onChange(tab.id)}
            type="button"
          >
            {isActive && !reduceMotion && (
              <motion.div
                layoutId="active-tab-indicator"
                className="tab-active-indicator"
                transition={{ type: 'tween', duration: .42, ease: [.16, 1, .3, 1] }}
              />
            )}
            <span style={{ position: 'relative', zIndex: 1, display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              {tab.icon}
              <span>{tab.label}</span>
              {tab.badge !== undefined && (
                <span
                  className="mono"
                  style={{
                    fontSize: '11px',
                    padding: '1px 6px',
                    borderRadius: 'var(--r-full)',
                    background: isActive ? 'var(--accent)' : 'var(--surface-card)',
                    color: isActive ? 'var(--on-accent)' : 'var(--muted)',
                    fontWeight: 600,
                  }}
                >
                  {tab.badge}
                </span>
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

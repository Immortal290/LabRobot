/**
 * RobotStateCard — Compact robot emotion + state indicator widget.
 *
 * Shows:
 *   - Color-coded state badge with emoji
 *   - State label + description
 *   - Battery bar
 *   - Mission text
 *   - Optional: mini animated pulse indicator
 *
 * Props:
 *   state       – Current RobotState
 *   battery     – Battery percentage 0–100
 *   mission     – Current mission string from telemetry
 *   compact     – Smaller card variant (default: false)
 *   showBattery – Show battery bar (default: true)
 */

import React from 'react';
import { motion } from 'framer-motion';
import { Battery, Zap } from 'lucide-react';
import { getRobotStateConfig, RobotState, isErrorState } from '../lib/robotStateLibrary';

interface RobotStateCardProps {
  state:        RobotState;
  battery:      number;
  mission?:     string;
  compact?:     boolean;
  showBattery?: boolean;
  className?:   string;
  style?:       React.CSSProperties;
}

export const RobotStateCard: React.FC<RobotStateCardProps> = ({
  state,
  battery,
  mission,
  compact      = false,
  showBattery  = true,
  className    = '',
  style        = {},
}) => {
  const cfg       = getRobotStateConfig(state);
  const isError   = isErrorState(state);
  const isLowBat  = battery <= 20;

  const batteryColor =
    battery > 50 ? 'var(--accent-green)' :
    battery > 20 ? '#f59e0b' :
    'var(--accent-red)';

  if (compact) {
    // ── Compact inline badge ─────────────────────────────────
    return (
      <div
        className={className}
        style={{
          display:        'inline-flex',
          alignItems:     'center',
          gap:            '6px',
          padding:        '5px 12px',
          borderRadius:   '20px',
          background:     `${cfg.color}15`,
          border:         `1px solid ${cfg.color}40`,
          boxShadow:      isError ? `0 0 12px ${cfg.glowColor}` : 'none',
          fontSize:       '0.78rem',
          fontWeight:     700,
          color:          cfg.color,
          whiteSpace:     'nowrap',
          transition:     'all 0.4s ease',
          ...style,
        }}
      >
        {/* Pulsing dot */}
        <motion.div
          animate={{ scale: [1, 1.3, 1], opacity: [1, 0.6, 1] }}
          transition={{ repeat: Infinity, duration: isError ? 0.8 : 2 }}
          style={{
            width:        '7px',
            height:       '7px',
            borderRadius: '50%',
            background:   cfg.color,
            boxShadow:    `0 0 6px ${cfg.color}`,
            flexShrink:   0,
          }}
        />
        <span style={{ fontSize: '0.85rem' }}>{cfg.emoji}</span>
        <span>{cfg.label}</span>
        {showBattery && (
          <span style={{
            color:      batteryColor,
            fontFamily: 'var(--font-mono)',
            fontSize:   '0.72rem',
            fontWeight: 700,
            marginLeft: '2px',
          }}>
            {isLowBat ? '⚠️' : ''} {battery}%
          </span>
        )}
      </div>
    );
  }

  // ── Full card mode ───────────────────────────────────────────
  return (
    <div
      className={`glass-panel ${className}`}
      style={{
        border:     `1px solid ${cfg.color}40`,
        boxShadow:  isError ? `0 0 20px ${cfg.glowColor}` : 'var(--glass-shadow)',
        transition: 'all 0.4s ease',
        padding:    '20px',
        ...style,
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Pulsing state indicator */}
          <motion.div
            animate={{ scale: [1, 1.2, 1], opacity: [1, 0.5, 1] }}
            transition={{ repeat: Infinity, duration: isError ? 0.7 : 2 }}
            style={{
              width:        '12px',
              height:       '12px',
              borderRadius: '50%',
              background:   cfg.color,
              boxShadow:    `0 0 10px ${cfg.color}`,
              flexShrink:   0,
            }}
          />
          <span style={{ fontSize: '1.1rem' }}>{cfg.emoji}</span>
          <span style={{
            fontWeight:  700,
            fontSize:    '0.95rem',
            color:       cfg.color,
            letterSpacing: '0.5px',
          }}>
            {cfg.label}
          </span>
        </div>

        {/* State badge */}
        <span style={{
          padding:    '3px 10px',
          borderRadius: '20px',
          background: `${cfg.color}18`,
          border:     `1px solid ${cfg.color}35`,
          fontSize:   '0.72rem',
          fontWeight: 700,
          color:      cfg.color,
          letterSpacing: '0.5px',
          textTransform: 'uppercase',
        }}>
          {cfg.dashboardLabel}
        </span>
      </div>

      {/* Description */}
      <p style={{
        fontSize:  '0.82rem',
        color:     'var(--text-secondary)',
        marginBottom: '14px',
        lineHeight: 1.4,
      }}>
        {cfg.userMessage}
      </p>

      {/* Mission text */}
      {mission && (
        <div style={{
          fontSize:    '0.78rem',
          color:       '#fff',
          fontFamily:  'var(--font-mono)',
          background:  'rgba(0,0,0,0.2)',
          padding:     '6px 10px',
          borderRadius: '8px',
          border:      '1px solid rgba(255,255,255,0.05)',
          marginBottom: '12px',
          overflow:    'hidden',
          textOverflow: 'ellipsis',
          whiteSpace:  'nowrap',
        }}>
          <span style={{ color: 'var(--text-secondary)' }}>MISSION: </span>
          {mission}
        </div>
      )}

      {/* Battery bar */}
      {showBattery && (
        <div>
          <div style={{
            display:       'flex',
            justifyContent:'space-between',
            alignItems:    'center',
            marginBottom:  '6px',
            fontSize:      '0.75rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-secondary)' }}>
              {battery <= 20 ? <Zap size={12} color="var(--accent-red)" /> : <Battery size={12} />}
              <span>Battery</span>
            </div>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontWeight: 700,
              color:      batteryColor,
            }}>
              {battery.toFixed(0)}%
            </span>
          </div>
          <div style={{
            height:       '5px',
            background:   'rgba(255,255,255,0.06)',
            borderRadius: '3px',
            overflow:     'hidden',
          }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${battery}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              style={{
                height:     '100%',
                background: batteryColor,
                borderRadius: '3px',
                boxShadow:  `0 0 6px ${batteryColor}`,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default RobotStateCard;

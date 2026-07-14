import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export type RobotState =
  | 'idle' | 'request_received' | 'validating' | 'task_assigned'
  | 'navigating' | 'arrived' | 'panel_open' | 'waiting_pickup'
  | 'pickup_confirmed' | 'returning' | 'completed'
  | 'low_battery' | 'blocked' | 'lock_failure' | 'timeout' | 'error';

interface RobotAvatarProps {
  state: RobotState;
  size?: number;
}

const STATE_CONFIG: Record<RobotState, {
  label: string;
  emoji: string;
  bodyColor: string;
  glowColor: string;
  eyeColor: string;
  badgeColor: string;
  mouthType: 'smile' | 'flat' | 'frown' | 'open' | 'grin';
  animate: boolean;
  pulse: boolean;
}> = {
  idle:             { label: 'Idle at Base',        emoji: '😴', bodyColor: '#1e293b', glowColor: 'rgba(148,163,184,0.3)', eyeColor: '#64748b', badgeColor: '#475569', mouthType: 'flat',   animate: false, pulse: false },
  request_received: { label: 'Request Received',    emoji: '👀', bodyColor: '#1e3a5f', glowColor: 'rgba(251,191,36,0.4)',  eyeColor: '#fbbf24', badgeColor: '#f59e0b', mouthType: 'open',   animate: true,  pulse: true  },
  validating:       { label: 'Validating…',         emoji: '🤔', bodyColor: '#1e3a5f', glowColor: 'rgba(251,146,60,0.3)',  eyeColor: '#fb923c', badgeColor: '#f97316', mouthType: 'flat',   animate: true,  pulse: false },
  task_assigned:    { label: 'Task Assigned',        emoji: '✅', bodyColor: '#0f3b2d', glowColor: 'rgba(16,185,129,0.4)', eyeColor: '#10b981', badgeColor: '#059669', mouthType: 'smile',  animate: false, pulse: true  },
  navigating:       { label: 'Navigating',           emoji: '🚀', bodyColor: '#0a2040', glowColor: 'rgba(6,182,212,0.5)',  eyeColor: '#06b6d4', badgeColor: '#0891b2', mouthType: 'grin',   animate: true,  pulse: true  },
  arrived:          { label: 'Arrived!',             emoji: '🎯', bodyColor: '#0f3b2d', glowColor: 'rgba(16,185,129,0.5)', eyeColor: '#10b981', badgeColor: '#059669', mouthType: 'grin',   animate: false, pulse: true  },
  panel_open:       { label: 'Panel Open',           emoji: '📦', bodyColor: '#2e1065', glowColor: 'rgba(139,92,246,0.5)', eyeColor: '#a78bfa', badgeColor: '#7c3aed', mouthType: 'open',   animate: true,  pulse: true  },
  waiting_pickup:   { label: 'Waiting for Pickup',  emoji: '⏳', bodyColor: '#3b1c08', glowColor: 'rgba(251,146,60,0.4)', eyeColor: '#fb923c', badgeColor: '#ea580c', mouthType: 'flat',   animate: true,  pulse: true  },
  pickup_confirmed: { label: 'Pickup Confirmed!',   emoji: '😊', bodyColor: '#0f3b2d', glowColor: 'rgba(16,185,129,0.6)', eyeColor: '#10b981', badgeColor: '#059669', mouthType: 'grin',   animate: false, pulse: true  },
  returning:        { label: 'Returning to Base',   emoji: '🏠', bodyColor: '#0a2040', glowColor: 'rgba(37,99,235,0.5)',  eyeColor: '#3b82f6', badgeColor: '#2563eb', mouthType: 'smile',  animate: true,  pulse: false },
  completed:        { label: 'Mission Complete!',   emoji: '🏆', bodyColor: '#0f3b2d', glowColor: 'rgba(16,185,129,0.6)', eyeColor: '#34d399', badgeColor: '#10b981', mouthType: 'grin',   animate: false, pulse: true  },
  low_battery:      { label: 'Low Battery',         emoji: '🔋', bodyColor: '#2d0a0a', glowColor: 'rgba(244,63,94,0.4)', eyeColor: '#f43f5e', badgeColor: '#e11d48', mouthType: 'frown',  animate: true,  pulse: true  },
  blocked:          { label: 'Path Blocked',        emoji: '😤', bodyColor: '#2d1a0a', glowColor: 'rgba(251,146,60,0.5)', eyeColor: '#fb923c', badgeColor: '#ea580c', mouthType: 'frown',  animate: true,  pulse: true  },
  lock_failure:     { label: 'Lock Failure!',       emoji: '❌', bodyColor: '#2d0a0a', glowColor: 'rgba(244,63,94,0.6)', eyeColor: '#f43f5e', badgeColor: '#e11d48', mouthType: 'frown',  animate: true,  pulse: true  },
  timeout:          { label: 'Pickup Timeout',      emoji: '😟', bodyColor: '#2d1a0a', glowColor: 'rgba(244,63,94,0.4)', eyeColor: '#f87171', badgeColor: '#dc2626', mouthType: 'frown',  animate: true,  pulse: false },
  error:            { label: 'Robot Error',         emoji: '💀', bodyColor: '#2d0a0a', glowColor: 'rgba(244,63,94,0.7)', eyeColor: '#f43f5e', badgeColor: '#9f1239', mouthType: 'frown',  animate: true,  pulse: true  },
};

const MouthPath: Record<string, string> = {
  smile:  'M 6 10 Q 10 14 14 10',
  flat:   'M 6 11 L 14 11',
  frown:  'M 6 14 Q 10 10 14 14',
  open:   'M 7 10 Q 10 15 13 10',
  grin:   'M 5 10 Q 10 16 15 10',
};

export const RobotAvatar: React.FC<RobotAvatarProps> = ({ state, size = 120 }) => {
  const cfg = STATE_CONFIG[state] || STATE_CONFIG.idle;

  const bodyAnimate = cfg.animate
    ? { y: [0, -4, 0] }
    : { y: 0 };
  const bodyTransition = cfg.animate
    ? { repeat: Infinity, duration: 1.5, ease: 'easeInOut' as const }
    : {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
      {/* Glow ring */}
      <div style={{ position: 'relative', width: size, height: size }}>
        {cfg.pulse && (
          <motion.div
            animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.2, 0.5] }}
            transition={{ repeat: Infinity, duration: 2 }}
            style={{
              position: 'absolute', inset: -8, borderRadius: '50%',
              background: cfg.glowColor,
              filter: 'blur(10px)',
            }}
          />
        )}

        <motion.svg
          width={size} height={size} viewBox="0 0 80 90"
          animate={bodyAnimate}
          transition={bodyTransition}
          style={{ position: 'relative', zIndex: 1, filter: `drop-shadow(0 0 12px ${cfg.glowColor})` }}
        >
          {/* Antenna */}
          <motion.line x1="40" y1="5" x2="40" y2="15"
            stroke={cfg.eyeColor} strokeWidth="2.5" strokeLinecap="round"
            animate={cfg.animate ? { y1: [5, 3, 5] } : {}}
            transition={{ repeat: Infinity, duration: 1.5 }}
          />
          <motion.circle cx="40" cy="4" r="3.5" fill={cfg.eyeColor}
            animate={cfg.pulse ? { r: [3.5, 5, 3.5], opacity: [1, 0.6, 1] } : {}}
            transition={{ repeat: Infinity, duration: 1.2 }}
          />

          {/* Head */}
          <rect x="12" y="14" width="56" height="38" rx="14" ry="14"
            fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="2"
            style={{ filter: 'brightness(1.3)' }}
          />

          {/* Eye sockets */}
          <rect x="18" y="22" width="18" height="14" rx="4" ry="4" fill="rgba(0,0,0,0.5)" />
          <rect x="44" y="22" width="18" height="14" rx="4" ry="4" fill="rgba(0,0,0,0.5)" />

          {/* Eyes (pupils) */}
          <AnimatePresence>
            <motion.circle
              key={`eye-l-${state}`}
              cx="27" cy="29" r="5"
              fill={cfg.eyeColor}
              initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
              transition={{ type: 'spring', stiffness: 300 }}
              style={{ filter: `drop-shadow(0 0 4px ${cfg.eyeColor})` }}
            />
            <motion.circle
              key={`eye-r-${state}`}
              cx="53" cy="29" r="5"
              fill={cfg.eyeColor}
              initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}
              transition={{ type: 'spring', stiffness: 300 }}
              style={{ filter: `drop-shadow(0 0 4px ${cfg.eyeColor})` }}
            />
          </AnimatePresence>

          {/* Blinking animation overlay */}
          {cfg.animate && (
            <>
              <motion.rect x="18" y="22" width="18" height="14" rx="4" ry="4"
                fill={cfg.bodyColor}
                animate={{ scaleY: [0, 1, 0] }}
                transition={{ repeat: Infinity, duration: 3, times: [0, 0.1, 0.2] }}
                style={{ transformOrigin: '27px 29px' }}
              />
              <motion.rect x="44" y="22" width="18" height="14" rx="4" ry="4"
                fill={cfg.bodyColor}
                animate={{ scaleY: [0, 1, 0] }}
                transition={{ repeat: Infinity, duration: 3, delay: 0.05, times: [0, 0.1, 0.2] }}
                style={{ transformOrigin: '53px 29px' }}
              />
            </>
          )}

          {/* Mouth */}
          <AnimatePresence mode="wait">
            <motion.path
              key={`mouth-${state}`}
              d={`M ${MouthPath[cfg.mouthType].split(' ').slice(0).join(' ')}`}
              fill="none"
              stroke={cfg.eyeColor}
              strokeWidth="2.5"
              strokeLinecap="round"
              transform="translate(20, 26)"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 1 }}
              exit={{ pathLength: 0, opacity: 0 }}
              transition={{ duration: 0.4 }}
            />
          </AnimatePresence>

          {/* Cheek blush (happy states) */}
          {(state === 'completed' || state === 'pickup_confirmed' || state === 'arrived') && (
            <>
              <ellipse cx="21" cy="40" rx="5" ry="3" fill="rgba(251,113,133,0.25)" />
              <ellipse cx="59" cy="40" rx="5" ry="3" fill="rgba(251,113,133,0.25)" />
            </>
          )}

          {/* Warning X eyes (error states) */}
          {(state === 'error' || state === 'lock_failure') && (
            <>
              <line x1="21" y1="25" x2="33" y2="37" stroke="#f43f5e" strokeWidth="3" strokeLinecap="round" />
              <line x1="33" y1="25" x2="21" y2="37" stroke="#f43f5e" strokeWidth="3" strokeLinecap="round" />
              <line x1="47" y1="25" x2="59" y2="37" stroke="#f43f5e" strokeWidth="3" strokeLinecap="round" />
              <line x1="59" y1="25" x2="47" y2="37" stroke="#f43f5e" strokeWidth="3" strokeLinecap="round" />
            </>
          )}

          {/* Body */}
          <rect x="18" y="54" width="44" height="28" rx="8" ry="8"
            fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="1.5"
            style={{ opacity: 0.9 }}
          />

          {/* Chest panel */}
          <rect x="27" y="60" width="26" height="14" rx="4" ry="4"
            fill="rgba(0,0,0,0.3)" stroke={`${cfg.eyeColor}66`} strokeWidth="1"
          />

          {/* Status light on chest */}
          <motion.circle cx="40" cy="67" r="4"
            fill={cfg.eyeColor}
            animate={cfg.pulse ? { opacity: [1, 0.3, 1], r: [4, 5.5, 4] } : { opacity: 1 }}
            transition={{ repeat: Infinity, duration: 1.2 }}
            style={{ filter: `drop-shadow(0 0 6px ${cfg.eyeColor})` }}
          />

          {/* Arms */}
          <rect x="4" y="56" width="12" height="20" rx="6" ry="6"
            fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="1.5"
          />
          <rect x="64" y="56" width="12" height="20" rx="6" ry="6"
            fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="1.5"
          />

          {/* Wheels */}
          <ellipse cx="28" cy="84" rx="8" ry="5" fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="1.5" />
          <ellipse cx="52" cy="84" rx="8" ry="5" fill={cfg.bodyColor} stroke={cfg.eyeColor} strokeWidth="1.5" />

          {/* Wheel spin during navigation */}
          {(state === 'navigating' || state === 'returning') && (
            <>
              <motion.line x1="20" y1="84" x2="36" y2="84"
                stroke={cfg.eyeColor} strokeWidth="1" strokeDasharray="3 3"
                animate={{ strokeDashoffset: [0, -12] }}
                transition={{ repeat: Infinity, duration: 0.5, ease: 'linear' }}
              />
              <motion.line x1="44" y1="84" x2="60" y2="84"
                stroke={cfg.eyeColor} strokeWidth="1" strokeDasharray="3 3"
                animate={{ strokeDashoffset: [0, -12] }}
                transition={{ repeat: Infinity, duration: 0.5, ease: 'linear' }}
              />
            </>
          )}
        </motion.svg>
      </div>

      {/* State label badge */}
      <motion.div
        key={state}
        initial={{ opacity: 0, y: 6, scale: 0.9 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.3 }}
        style={{
          background: `${cfg.badgeColor}22`,
          border: `1px solid ${cfg.badgeColor}66`,
          color: cfg.eyeColor,
          padding: '4px 12px',
          borderRadius: '20px',
          fontSize: '0.8rem',
          fontWeight: 700,
          letterSpacing: '0.5px',
          textAlign: 'center',
          whiteSpace: 'nowrap',
        }}
      >
        {cfg.emoji} {cfg.label}
      </motion.div>
    </div>
  );
};

export const robotStateFromTelemetry = (
  status: string,
  battery: number,
  deliveryStatus?: string
): RobotState => {
  if (battery < 15) return 'low_battery';

  const s = (deliveryStatus || status || '').toLowerCase();
  const m: Record<string, RobotState> = {
    idle:             'idle',
    standby:          'idle',
    pending:          'request_received',
    validating:       'validating',
    assigned:         'task_assigned',
    navigating:       'navigating',
    active:           'navigating',
    arrived:          'arrived',
    panel_open:       'panel_open',
    waiting_pickup:   'waiting_pickup',
    pickup_confirmed: 'pickup_confirmed',
    completed:        'completed',
    returning:        'returning',
    cancelled:        'idle',
    blocked:          'blocked',
    lock_failure:     'lock_failure',
    pickup_timeout:   'timeout',
    failed:           'error',
    error:            'error',
    offline:          'error',
  };
  return m[s] || 'idle';
};

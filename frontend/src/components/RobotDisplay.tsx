/**
 * RobotDisplay — Drop-in animated video display for the LabRobot screen.
 *
 * Props:
 *   state        – A RobotState enum value (or raw string). Drives which
 *                  video plays.  Defaults to RobotState.IDLE.
 *   showLabel    – Show/hide the state label badge.  Default: true.
 *   showStatus   – Show/hide the description text.    Default: true.
 *   width / height – CSS dimensions of the display panel.
 *   onVideoEnd   – Callback when a non-looping video finishes (e.g. task
 *                  success / failed) so the parent can transition back to
 *                  IDLE automatically.
 *
 * Example (inside AdminDashboard or any page):
 *
 *   import { RobotDisplay } from '../components/RobotDisplay';
 *   import { mapTelemetryToState, RobotState } from '../lib/robotStateLibrary';
 *
 *   const robotState = mapTelemetryToState(
 *     telemetry.status,
 *     telemetry.mission,
 *     telemetry.battery
 *   );
 *
 *   <RobotDisplay
 *     state={robotState}
 *     onVideoEnd={() => setRobotState(RobotState.IDLE)}
 *   />
 */

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getRobotStateConfig, RobotState } from '../lib/robotStateLibrary';
import type { RobotStateConfig } from '../lib/robotStateLibrary';

// ─── Icon map: state → SVG path data ─────────────────────────────────────────
const STATE_ICONS: Partial<Record<RobotState, string>> = {
  [RobotState.IDLE]:         'M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 14a1 1 0 1 1 0-2 1 1 0 0 1 0 2zm1-4H11V8h2v4z',
  [RobotState.NAVIGATING]:   'M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5',
  [RobotState.TASK_SUCCESS]: 'M20 6L9 17l-5-5',
  [RobotState.TASK_FAILED]:  'M18 6 6 18M6 6l12 12',
  [RobotState.CHARGING]:     'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  [RobotState.LOW_BATTERY]:  'M6 7H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2m14-9a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1M6 7h12v10H6V7zm5 4h2v2h-2v-2z',
};

// ─── Prop types ───────────────────────────────────────────────────────────────
interface RobotDisplayProps {
  state?:       RobotState | string;
  showLabel?:   boolean;
  showStatus?:  boolean;
  width?:       string;
  height?:      string;
  onVideoEnd?:  () => void;
  className?:   string;
}

// ─── Component ────────────────────────────────────────────────────────────────
export const RobotDisplay: React.FC<RobotDisplayProps> = ({
  state      = RobotState.IDLE,
  showLabel  = true,
  showStatus = true,
  width      = '100%',
  height     = '360px',
  onVideoEnd,
  className  = '',
}) => {
  const videoRef                                = useRef<HTMLVideoElement>(null);
  const [config, setConfig]                     = useState<RobotStateConfig>(
    getRobotStateConfig(state)
  );
  const [isTransitioning, setIsTransitioning]   = useState(false);
  const [scanLine, setScanLine]                 = useState(0);

  // Update config whenever the state prop changes
  useEffect(() => {
    const next = getRobotStateConfig(state);
    if (next.videoUrl === config.videoUrl) return;  // same video, no swap needed

    setIsTransitioning(true);
    const timer = setTimeout(() => {
      setConfig(next);
      setIsTransitioning(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [state]);

  // Swap the video src whenever config changes
  useEffect(() => {
    const vid = videoRef.current;
    if (!vid) return;

    vid.src    = config.videoUrl;
    vid.loop   = config.loop;
    vid.load();
    vid.play().catch(() => {
      // Autoplay was blocked — muted autoplay is allowed in all modern browsers
      vid.muted = true;
      vid.play();
    });
  }, [config]);

  // Animate scan-line for futuristic feel
  useEffect(() => {
    const id = setInterval(() => {
      setScanLine(prev => (prev + 1) % 100);
    }, 30);
    return () => clearInterval(id);
  }, []);

  const handleVideoEnd = () => {
    if (!config.loop && onVideoEnd) {
      onVideoEnd();
    }
  };

  return (
    <div
      className={`robot-display ${className}`}
      style={{
        width,
        height,
        position:     'relative',
        borderRadius: '20px',
        overflow:     'hidden',
        background:   '#000',
        border:       `2px solid ${config.color}`,
        boxShadow:    `0 0 30px ${config.glowColor}, inset 0 0 30px rgba(0,0,0,0.8)`,
        transition:   'border-color 0.5s ease, box-shadow 0.5s ease',
      }}
    >
      {/* ── Video Player ─────────────────────────────────────── */}
      <AnimatePresence>
        <motion.video
          key={config.videoUrl}
          ref={videoRef}
          src={config.videoUrl}
          loop={config.loop}
          muted
          playsInline
          autoPlay
          onEnded={handleVideoEnd}
          initial={{ opacity: 0 }}
          animate={{ opacity: isTransitioning ? 0 : 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          style={{
            width:      '100%',
            height:     '100%',
            objectFit:  'cover',
            display:    'block',
          }}
        />
      </AnimatePresence>

      {/* ── Futuristic overlay: scan-line ────────────────────── */}
      <div
        aria-hidden="true"
        style={{
          position:         'absolute',
          inset:            0,
          background:       `linear-gradient(transparent ${scanLine}%, rgba(255,255,255,0.04) ${scanLine}%, rgba(255,255,255,0.04) ${scanLine + 1}%, transparent ${scanLine + 1}%)`,
          pointerEvents:    'none',
        }}
      />

      {/* ── Overlay: vignette ────────────────────────────────── */}
      <div
        aria-hidden="true"
        style={{
          position:      'absolute',
          inset:         0,
          background:    'radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,0.6) 100%)',
          pointerEvents: 'none',
        }}
      />

      {/* ── Corner decorations ───────────────────────────────── */}
      {(['tl','tr','bl','br'] as const).map(corner => (
        <div
          key={corner}
          aria-hidden="true"
          style={{
            position:    'absolute',
            width:       '20px',
            height:      '20px',
            borderColor: config.color,
            borderStyle: 'solid',
            borderWidth: 0,
            ...(corner === 'tl' ? { top: 8, left: 8,  borderTopWidth: 2,    borderLeftWidth: 2  } : {}),
            ...(corner === 'tr' ? { top: 8, right: 8,  borderTopWidth: 2,    borderRightWidth: 2 } : {}),
            ...(corner === 'bl' ? { bottom: 8, left: 8, borderBottomWidth: 2, borderLeftWidth: 2  } : {}),
            ...(corner === 'br' ? { bottom: 8, right: 8, borderBottomWidth: 2, borderRightWidth: 2 } : {}),
          }}
        />
      ))}

      {/* ── State badge (top-left) ────────────────────────────── */}
      {showLabel && (
        <motion.div
          key={config.state}
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.35, delay: 0.1 }}
          style={{
            position:       'absolute',
            top:            '16px',
            left:           '16px',
            display:        'flex',
            alignItems:     'center',
            gap:            '8px',
            background:     'rgba(0,0,0,0.65)',
            backdropFilter: 'blur(10px)',
            border:         `1px solid ${config.color}`,
            borderRadius:   '30px',
            padding:        '6px 14px',
            color:          config.color,
            fontSize:       '0.8rem',
            fontWeight:     700,
            letterSpacing:  '1.5px',
            textTransform:  'uppercase',
            boxShadow:      `0 0 12px ${config.glowColor}`,
          }}
        >
          {/* State icon */}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke={config.color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          >
            <path d={STATE_ICONS[config.state] ?? STATE_ICONS[RobotState.IDLE]} />
          </svg>
          {config.label}
        </motion.div>
      )}

      {/* ── Pulsing status dot (top-right) ───────────────────── */}
      <div
        style={{
          position:     'absolute',
          top:          '20px',
          right:        '20px',
          width:        '10px',
          height:       '10px',
          borderRadius: '50%',
          background:   config.color,
          boxShadow:    `0 0 8px ${config.color}`,
          animation:    'pulse-glow 2s infinite',
        }}
      />

      {/* ── Status description bar (bottom) ──────────────────── */}
      {showStatus && (
        <motion.div
          key={config.state + '-desc'}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, delay: 0.15 }}
          style={{
            position:       'absolute',
            bottom:         0,
            left:           0,
            right:          0,
            padding:        '16px 20px',
            background:     'linear-gradient(transparent, rgba(0,0,0,0.85))',
            backdropFilter: 'blur(4px)',
            display:        'flex',
            flexDirection:  'column',
            gap:            '4px',
          }}
        >
          <span style={{
            color:         '#fff',
            fontSize:      '0.75rem',
            opacity:       0.5,
            letterSpacing: '2px',
            textTransform: 'uppercase',
            fontFamily:    'var(--font-mono, monospace)',
          }}>
            ROBOT STATUS
          </span>
          <span style={{
            color:      '#fff',
            fontSize:   '0.9rem',
            fontWeight: 500,
            lineHeight: '1.4',
          }}>
            {config.description}
          </span>
        </motion.div>
      )}
    </div>
  );
};

export default RobotDisplay;

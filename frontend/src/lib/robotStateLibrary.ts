// ============================================================
//  LabRobot — Robot State Animation Library
//  Maps every robot state to its corresponding animation video.
//
//  HOW TO USE (hardware / software integration):
//
//  1.  Import `getRobotStateConfig` and `RobotState`
//  2.  Call  getRobotStateConfig(RobotState.IDLE)  (or any state)
//      to get the full config object.
//  3.  Use the `videoUrl` property to play the correct clip.
//
//  To add a new state:
//    a)  Add a key to `RobotState`
//    b)  Add its entry to `ROBOT_STATE_REGISTRY`
//    c)  Drop the video file into  public/videos/
// ============================================================

/** All possible robot operational states (const object — compatible with erasableSyntaxOnly). */
export const RobotState = {
  IDLE:         'idle',
  NAVIGATING:   'navigating',
  TASK_SUCCESS: 'task_successful',
  TASK_FAILED:  'task_failed',
  CHARGING:     'charging',
  LOW_BATTERY:  'low_battery',
} as const;

/** Union type derived from the RobotState map. */
export type RobotState = (typeof RobotState)[keyof typeof RobotState];

/** Full configuration for a single robot state. */
export interface RobotStateConfig {
  /** Unique state identifier (matches a RobotState value). */
  state: RobotState;

  /** Human-readable label shown on the display screen. */
  label: string;

  /** Brief description of what this state means. */
  description: string;

  /**
   * Path to the animation video, relative to the public/ folder.
   * In the browser this resolves to e.g. /videos/idle.mp4
   */
  videoUrl: string;

  /**
   * Whether the video should loop continuously.
   * Ambient states (idle, charging, navigating) loop.
   * Event states (success, failed) play once.
   */
  loop: boolean;

  /**
   * Accent colour associated with this state.
   * Used for overlay borders / glow effects on the display.
   */
  color: string;

  /** RGBA glow colour for the video border shadow. */
  glowColor: string;

  /**
   * Priority level — higher numbers take precedence when
   * multiple states are active simultaneously.
   *   0 = lowest (idle)
   *   9 = highest (task_failed / emergency)
   */
  priority: number;
}

// ─────────────────────────────────────────────────────────────
//  THE REGISTRY — add / edit states here
// ─────────────────────────────────────────────────────────────

export const ROBOT_STATE_REGISTRY: Record<RobotState, RobotStateConfig> = {

  [RobotState.IDLE]: {
    state:       RobotState.IDLE,
    label:       'Standby',
    description: 'Robot is idle and waiting for a new task.',
    videoUrl:    '/videos/idle.mp4',
    loop:        true,
    color:       '#06b6d4',
    glowColor:   'rgba(6,182,212,0.35)',
    priority:    0,
  },

  [RobotState.NAVIGATING]: {
    state:       RobotState.NAVIGATING,
    label:       'Navigating',
    description: 'Robot is moving from its current position to the goal.',
    videoUrl:    '/videos/navigation.mp4',
    loop:        true,
    color:       '#2563eb',
    glowColor:   'rgba(37,99,235,0.35)',
    priority:    3,
  },

  [RobotState.TASK_SUCCESS]: {
    state:       RobotState.TASK_SUCCESS,
    label:       'Task Complete',
    description: 'The assigned delivery task was completed successfully.',
    videoUrl:    '/videos/task_successful.mp4',
    loop:        false,
    color:       '#10b981',
    glowColor:   'rgba(16,185,129,0.40)',
    priority:    5,
  },

  [RobotState.TASK_FAILED]: {
    state:       RobotState.TASK_FAILED,
    label:       'Task Failed',
    description: 'The assigned task could not be completed. Manual intervention required.',
    videoUrl:    '/videos/task_failed.mp4',
    loop:        false,
    color:       '#f43f5e',
    glowColor:   'rgba(244,63,94,0.45)',
    priority:    9,
  },

  [RobotState.CHARGING]: {
    state:       RobotState.CHARGING,
    label:       'Charging',
    description: 'Robot is docked and battery is being recharged.',
    videoUrl:    '/videos/charging.mp4',
    loop:        true,
    color:       '#10b981',
    glowColor:   'rgba(16,185,129,0.35)',
    priority:    1,
  },

  [RobotState.LOW_BATTERY]: {
    state:       RobotState.LOW_BATTERY,
    label:       'Low Battery',
    description: 'Battery level is critically low. Robot is returning to dock.',
    videoUrl:    '/videos/lowbattery.mp4',
    loop:        true,
    color:       '#f59e0b',
    glowColor:   'rgba(245,158,11,0.40)',
    priority:    7,
  },
};

// ─────────────────────────────────────────────────────────────
//  HELPER FUNCTIONS
// ─────────────────────────────────────────────────────────────

/**
 * Returns the full config for a given robot state.
 * Falls back to IDLE if an unknown state string is provided.
 */
export function getRobotStateConfig(state: RobotState | string): RobotStateConfig {
  const config = ROBOT_STATE_REGISTRY[state as RobotState];
  if (!config) {
    console.warn(`[RobotStateLibrary] Unknown state "${state}", falling back to IDLE.`);
    return ROBOT_STATE_REGISTRY[RobotState.IDLE];
  }
  return config;
}

/**
 * Maps a raw telemetry payload from the backend WebSocket
 * to one of the RobotState values.
 *
 * Usage:
 *   const state = mapTelemetryToState(data.status, data.mission, data.battery);
 *   const config = getRobotStateConfig(state);
 */
export function mapTelemetryToState(
  status:  string,
  mission: string,
  battery: number,
): RobotState {
  // ── Critical battery check (highest priority ambient state) ──
  if (battery <= 15) return RobotState.LOW_BATTERY;

  // ── Mission / status string mapping ────────────────────────
  const m = mission.toLowerCase();
  const s = status.toLowerCase();

  if (m.includes('charging') || s === 'charging') return RobotState.CHARGING;

  if (
    m.includes('delivering') ||
    m.includes('navigating')  ||
    m.includes('returning')   ||
    s  === 'active'
  ) {
    return RobotState.NAVIGATING;
  }

  if (m.includes('failed') || m.includes('error') || s === 'failed') {
    return RobotState.TASK_FAILED;
  }

  if (m.includes('complete') || m.includes('success') || m.includes('delivered')) {
    return RobotState.TASK_SUCCESS;
  }

  // ── Default: idle / standby ─────────────────────────────────
  return RobotState.IDLE;
}

/**
 * Returns an ordered list of all state configs sorted by priority (high → low).
 * Useful for building settings UIs or debug panels.
 */
export function getAllStatesSorted(): RobotStateConfig[] {
  return Object.values(ROBOT_STATE_REGISTRY)
    .sort((a, b) => b.priority - a.priority);
}

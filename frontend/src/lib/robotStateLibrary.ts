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
  // ── Ambient / persistent states ──────────────────────────
  IDLE:              'idle',
  NAVIGATING:        'navigating',
  RETURNING:         'returning',
  CHARGING:          'charging',
  LOW_BATTERY:       'low_battery',

  // ── Request lifecycle states ──────────────────────────────
  REQUEST_RECEIVED:  'request_received',
  VALIDATING:        'validating',
  TASK_ASSIGNED:     'task_assigned',

  // ── Delivery execution states ─────────────────────────────
  ARRIVED:           'arrived',
  PANEL_OPEN:        'panel_open',
  WAITING_PICKUP:    'waiting_pickup',
  PICKUP_CONFIRMED:  'pickup_confirmed',

  // ── Completion states ─────────────────────────────────────
  TASK_SUCCESS:      'task_successful',
  TASK_FAILED:       'task_failed',

  // ── Error / warning states ────────────────────────────────
  OBSTACLE_BLOCKED:  'obstacle_blocked',
  LOCK_FAILURE:      'lock_failure',
  TIMEOUT:           'timeout',
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

  /**
   * Emoji / icon representation for compact badges in the UI.
   */
  emoji: string;

  /**
   * User-facing message shown on the mobile portal.
   */
  userMessage: string;

  /**
   * Admin dashboard label (shorter than label).
   */
  dashboardLabel: string;
}

// ─────────────────────────────────────────────────────────────
//  THE REGISTRY — add / edit states here
// ─────────────────────────────────────────────────────────────

export const ROBOT_STATE_REGISTRY: Record<RobotState, RobotStateConfig> = {

  // ── IDLE ──────────────────────────────────────────────────
  [RobotState.IDLE]: {
    state:          RobotState.IDLE,
    label:          'Standby',
    description:    'Robot is idle and waiting for a new task.',
    videoUrl:       '/videos/idle.mp4',
    loop:           true,
    color:          '#06b6d4',
    glowColor:      'rgba(6,182,212,0.35)',
    priority:       0,
    emoji:          '🤖',
    userMessage:    'Robot is available and ready for your request.',
    dashboardLabel: 'Idle',
  },

  // ── REQUEST_RECEIVED ──────────────────────────────────────
  [RobotState.REQUEST_RECEIVED]: {
    state:          RobotState.REQUEST_RECEIVED,
    label:          'Request Received',
    description:    'Your delivery request has been received and queued.',
    videoUrl:       '/videos/idle.mp4',
    loop:           true,
    color:          '#06b6d4',
    glowColor:      'rgba(6,182,212,0.35)',
    priority:       1,
    emoji:          '📥',
    userMessage:    'Request received! Checking availability...',
    dashboardLabel: 'Request In',
  },

  // ── VALIDATING ────────────────────────────────────────────
  [RobotState.VALIDATING]: {
    state:          RobotState.VALIDATING,
    label:          'Validating',
    description:    'Checking inventory availability and robot readiness.',
    videoUrl:       '/videos/idle.mp4',
    loop:           true,
    color:          '#8b5cf6',
    glowColor:      'rgba(139,92,246,0.35)',
    priority:       2,
    emoji:          '🔍',
    userMessage:    'Verifying item availability and robot status...',
    dashboardLabel: 'Validating',
  },

  // ── TASK_ASSIGNED ─────────────────────────────────────────
  [RobotState.TASK_ASSIGNED]: {
    state:          RobotState.TASK_ASSIGNED,
    label:          'Task Assigned',
    description:    'Task has been sent to the robot. Robot is preparing.',
    videoUrl:       '/videos/idle.mp4',
    loop:           true,
    color:          '#f59e0b',
    glowColor:      'rgba(245,158,11,0.40)',
    priority:       3,
    emoji:          '📋',
    userMessage:    'Task assigned! Robot is preparing for delivery.',
    dashboardLabel: 'Assigned',
  },

  // ── NAVIGATING ────────────────────────────────────────────
  [RobotState.NAVIGATING]: {
    state:          RobotState.NAVIGATING,
    label:          'Navigating',
    description:    'Robot is moving from its current position to the goal.',
    videoUrl:       '/videos/navigation.mp4',
    loop:           true,
    color:          '#2563eb',
    glowColor:      'rgba(37,99,235,0.35)',
    priority:       4,
    emoji:          '🚀',
    userMessage:    'Robot is on its way to your location!',
    dashboardLabel: 'In Transit',
  },

  // ── ARRIVED ───────────────────────────────────────────────
  [RobotState.ARRIVED]: {
    state:          RobotState.ARRIVED,
    label:          'Arrived',
    description:    'Robot has reached its destination and is ready for pickup.',
    videoUrl:       '/videos/task_successful.mp4',
    loop:           false,
    color:          '#10b981',
    glowColor:      'rgba(16,185,129,0.40)',
    priority:       6,
    emoji:          '📍',
    userMessage:    'Robot has arrived at your location!',
    dashboardLabel: 'Arrived',
  },

  // ── PANEL_OPEN ────────────────────────────────────────────
  [RobotState.PANEL_OPEN]: {
    state:          RobotState.PANEL_OPEN,
    label:          'Panel Open',
    description:    'Compartment is open. Please collect your equipment.',
    videoUrl:       '/videos/task_successful.mp4',
    loop:           true,
    color:          '#06b6d4',
    glowColor:      'rgba(6,182,212,0.45)',
    priority:       7,
    emoji:          '🔓',
    userMessage:    'Panel is open — please collect your item now!',
    dashboardLabel: 'Panel Open',
  },

  // ── WAITING_PICKUP ────────────────────────────────────────
  [RobotState.WAITING_PICKUP]: {
    state:          RobotState.WAITING_PICKUP,
    label:          'Waiting for Pickup',
    description:    'Robot is waiting for the user to collect the item.',
    videoUrl:       '/videos/task_successful.mp4',
    loop:           true,
    color:          '#f59e0b',
    glowColor:      'rgba(245,158,11,0.40)',
    priority:       7,
    emoji:          '⏳',
    userMessage:    'Waiting for you to collect your item...',
    dashboardLabel: 'Awaiting Pickup',
  },

  // ── PICKUP_CONFIRMED ──────────────────────────────────────
  [RobotState.PICKUP_CONFIRMED]: {
    state:          RobotState.PICKUP_CONFIRMED,
    label:          'Pickup Confirmed',
    description:    'Item collected successfully. Panel is closing.',
    videoUrl:       '/videos/task_successful.mp4',
    loop:           false,
    color:          '#10b981',
    glowColor:      'rgba(16,185,129,0.45)',
    priority:       5,
    emoji:          '✅',
    userMessage:    'Item collected! Thank you. Panel closing...',
    dashboardLabel: 'Picked Up',
  },

  // ── RETURNING ─────────────────────────────────────────────
  [RobotState.RETURNING]: {
    state:          RobotState.RETURNING,
    label:          'Returning to Base',
    description:    'Delivery complete. Robot is returning to its origin dock.',
    videoUrl:       '/videos/navigation.mp4',
    loop:           true,
    color:          '#2563eb',
    glowColor:      'rgba(37,99,235,0.35)',
    priority:       3,
    emoji:          '🏠',
    userMessage:    'Delivery complete! Robot is heading back to base.',
    dashboardLabel: 'Returning',
  },

  // ── TASK_SUCCESS ──────────────────────────────────────────
  [RobotState.TASK_SUCCESS]: {
    state:          RobotState.TASK_SUCCESS,
    label:          'Task Complete',
    description:    'The assigned delivery task was completed successfully.',
    videoUrl:       '/videos/task_successful.mp4',
    loop:           false,
    color:          '#10b981',
    glowColor:      'rgba(16,185,129,0.40)',
    priority:       5,
    emoji:          '🎉',
    userMessage:    'Delivery completed successfully!',
    dashboardLabel: 'Complete',
  },

  // ── TASK_FAILED ───────────────────────────────────────────
  [RobotState.TASK_FAILED]: {
    state:          RobotState.TASK_FAILED,
    label:          'Task Failed',
    description:    'The assigned task could not be completed. Manual intervention required.',
    videoUrl:       '/videos/task_failed.mp4',
    loop:           false,
    color:          '#f43f5e',
    glowColor:      'rgba(244,63,94,0.45)',
    priority:       9,
    emoji:          '❌',
    userMessage:    'Task failed. Please contact lab staff for assistance.',
    dashboardLabel: 'Failed',
  },

  // ── CHARGING ──────────────────────────────────────────────
  [RobotState.CHARGING]: {
    state:          RobotState.CHARGING,
    label:          'Charging',
    description:    'Robot is docked and battery is being recharged.',
    videoUrl:       '/videos/charging.mp4',
    loop:           true,
    color:          '#10b981',
    glowColor:      'rgba(16,185,129,0.35)',
    priority:       1,
    emoji:          '⚡',
    userMessage:    'Robot is currently charging. Please wait.',
    dashboardLabel: 'Charging',
  },

  // ── LOW_BATTERY ───────────────────────────────────────────
  [RobotState.LOW_BATTERY]: {
    state:          RobotState.LOW_BATTERY,
    label:          'Low Battery',
    description:    'Battery level is critically low. Robot is returning to dock.',
    videoUrl:       '/videos/lowbattery.mp4',
    loop:           true,
    color:          '#f59e0b',
    glowColor:      'rgba(245,158,11,0.40)',
    priority:       7,
    emoji:          '🔋',
    userMessage:    'Robot has low battery and cannot accept new tasks.',
    dashboardLabel: 'Low Battery',
  },

  // ── OBSTACLE_BLOCKED ──────────────────────────────────────
  [RobotState.OBSTACLE_BLOCKED]: {
    state:          RobotState.OBSTACLE_BLOCKED,
    label:          'Path Blocked',
    description:    'An obstacle is blocking the robot\'s path. Waiting to resolve.',
    videoUrl:       '/videos/task_failed.mp4',
    loop:           true,
    color:          '#f43f5e',
    glowColor:      'rgba(244,63,94,0.40)',
    priority:       8,
    emoji:          '🚧',
    userMessage:    'Robot path is blocked. Resolving obstacle...',
    dashboardLabel: 'Blocked',
  },

  // ── LOCK_FAILURE ──────────────────────────────────────────
  [RobotState.LOCK_FAILURE]: {
    state:          RobotState.LOCK_FAILURE,
    label:          'Lock Failure',
    description:    'Panel failed to close or lock correctly. Admin intervention required.',
    videoUrl:       '/videos/task_failed.mp4',
    loop:           false,
    color:          '#f43f5e',
    glowColor:      'rgba(244,63,94,0.45)',
    priority:       9,
    emoji:          '🔒',
    userMessage:    'Panel lock failure detected. Contacting admin...',
    dashboardLabel: 'Lock Error',
  },

  // ── TIMEOUT ───────────────────────────────────────────────
  [RobotState.TIMEOUT]: {
    state:          RobotState.TIMEOUT,
    label:          'Pickup Timeout',
    description:    'Pickup was not confirmed within the allowed time. Panel closing.',
    videoUrl:       '/videos/lowbattery.mp4',
    loop:           true,
    color:          '#f59e0b',
    glowColor:      'rgba(245,158,11,0.40)',
    priority:       8,
    emoji:          '⚠️',
    userMessage:    'Pickup timeout. Panel is closing for security.',
    dashboardLabel: 'Timeout',
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

  // ── Normalise strings ────────────────────────────────────
  const m = (mission || '').toLowerCase();
  const s = (status  || '').toLowerCase();

  // ── Error / blocked states (high priority) ───────────────
  if (m.includes('lock_fail') || m.includes('lock failure') || s === 'lock_failure') {
    return RobotState.LOCK_FAILURE;
  }
  if (m.includes('blocked') || m.includes('obstacle') || s === 'blocked') {
    return RobotState.OBSTACLE_BLOCKED;
  }
  if (m.includes('timeout') || s === 'timeout') {
    return RobotState.TIMEOUT;
  }

  // ── Task completion states ────────────────────────────────
  if (m.includes('failed') || m.includes('error') || s === 'failed') {
    return RobotState.TASK_FAILED;
  }
  if (m.includes('complete') || m.includes('success') || m.includes('delivered')) {
    return RobotState.TASK_SUCCESS;
  }

  // ── Pickup lifecycle states ───────────────────────────────
  if (m.includes('pickup_confirmed') || m.includes('pickup confirmed') || s === 'pickup_confirmed') {
    return RobotState.PICKUP_CONFIRMED;
  }
  if (m.includes('panel_open') || m.includes('panel open') || m.includes('unlocked') || s === 'panel_open') {
    return RobotState.PANEL_OPEN;
  }
  if (m.includes('waiting_pickup') || m.includes('waiting for pickup') || s === 'waiting_pickup') {
    return RobotState.WAITING_PICKUP;
  }
  if (m.includes('arrived') || s === 'arrived') {
    return RobotState.ARRIVED;
  }

  // ── Navigation states ─────────────────────────────────────
  if (m.includes('returning') || m.includes('return_to_base') || s === 'returning') {
    return RobotState.RETURNING;
  }
  if (
    m.includes('delivering') ||
    m.includes('navigating')  ||
    s === 'active'
  ) {
    return RobotState.NAVIGATING;
  }

  // ── Request lifecycle states ──────────────────────────────
  if (m.includes('task_assigned') || m.includes('task assigned') || s === 'task_assigned') {
    return RobotState.TASK_ASSIGNED;
  }
  if (m.includes('validating') || s === 'validating') {
    return RobotState.VALIDATING;
  }
  if (m.includes('request_received') || m.includes('request received') || s === 'request_received') {
    return RobotState.REQUEST_RECEIVED;
  }

  // ── Charging ──────────────────────────────────────────────
  if (m.includes('charging') || s === 'charging') return RobotState.CHARGING;

  // ── Default: idle / standby ─────────────────────────────
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

/**
 * Returns true if the given state represents an active (non-idle) delivery mission.
 */
export function isActiveDeliveryState(state: RobotState): boolean {
  return ([
    RobotState.TASK_ASSIGNED,
    RobotState.NAVIGATING,
    RobotState.ARRIVED,
    RobotState.PANEL_OPEN,
    RobotState.WAITING_PICKUP,
    RobotState.PICKUP_CONFIRMED,
    RobotState.RETURNING,
  ] as RobotState[]).includes(state);
}

/**
 * Returns true if the given state is an error / warning condition.
 */
export function isErrorState(state: RobotState): boolean {
  return ([
    RobotState.TASK_FAILED,
    RobotState.OBSTACLE_BLOCKED,
    RobotState.LOCK_FAILURE,
    RobotState.TIMEOUT,
    RobotState.LOW_BATTERY,
  ] as RobotState[]).includes(state);
}

/**
 * Maps a delivery status string from the backend to the expected robot workflow step index (0-6).
 * Used to drive the WorkflowTimeline component.
 */
export function deliveryStatusToStep(
  deliveryStatus: string,
  robotState: RobotState,
): number {
  const ds = (deliveryStatus || '').toLowerCase();
  if (ds === 'cancelled' || ds === 'failed') return -1;
  if (robotState === RobotState.IDLE && ds === 'completed') return 6; // returned to base
  if (robotState === RobotState.RETURNING) return 6;
  if (robotState === RobotState.PICKUP_CONFIRMED || ds === 'pickup_confirmed') return 5;
  if (robotState === RobotState.PANEL_OPEN || robotState === RobotState.WAITING_PICKUP) return 4;
  if (robotState === RobotState.ARRIVED) return 3;
  if (robotState === RobotState.NAVIGATING && ds === 'in_progress') return 2;
  if (robotState === RobotState.TASK_ASSIGNED || robotState === RobotState.VALIDATING) return 1;
  if (ds === 'pending' || robotState === RobotState.REQUEST_RECEIVED) return 0;
  return 0;
}

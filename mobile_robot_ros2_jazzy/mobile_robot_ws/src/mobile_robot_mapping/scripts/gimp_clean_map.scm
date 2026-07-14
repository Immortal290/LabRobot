; ═══════════════════════════════════════════════════════════════════════════
;  gimp_clean_map.scm — GIMP Script-Fu batch procedure for cleaning a
;  slam_toolbox / map_saver occupancy grid PGM.
;
;  What it does, in order:
;    1. Loads the map, forces grayscale
;    2. Despeckle (median-based) — removes salt-and-pepper noise: isolated
;       stray black pixels in free space, isolated white specks in walls
;    3. Re-quantizes every pixel to exactly ONE of the three canonical
;       occupancy-grid values:
;         0   = occupied (black)
;         205 = unknown  (gray)
;         254 = free     (white)
;       This is the important step GIMP's normal filters don't do on their
;       own — despeckling/blurring alone leaves semi-gray edge pixels, which
;       map_server / nav2 can misread as fractional occupancy probability
;       instead of a clean binary/unknown map.
;    4. Saves as a raw PGM (P5) — the format ROS map_server expects.
;
;  Not called directly — invoked via gimp_clean_map.sh, which passes in the
;  file paths and tuning parameters.
; ═══════════════════════════════════════════════════════════════════════════

(define (clean-map-batch infile outfile despeckle-radius black-cutoff white-cutoff)
  (let* ((image    (car (gimp-file-load RUN-NONINTERACTIVE infile infile)))
         (drawable (car (gimp-image-get-active-drawable image))))

    ; ── 1. Force grayscale ──────────────────────────────────────────────────
    (if (not (= (car (gimp-image-base-type image)) GRAY))
        (gimp-image-convert-grayscale image))
    (set! drawable (car (gimp-image-get-active-drawable image)))

    ; ── 2. Despeckle — median-based speckle/salt-and-pepper removal ────────
    ; type=1 (recursive median) gives stronger cleanup on scattered LIDAR
    ; noise than a single pass; radius controls how large a speckle cluster
    ; gets removed vs preserved as real geometry.
    (plug-in-despeckle RUN-NONINTERACTIVE image drawable
                        1                 ; DESPECKLE-RECURSIVE-MEDIAN
                        despeckle-radius
                        -1                ; black level (-1 = use full range)
                        256)              ; white level (256 = use full range)

    ; ── 3. Re-quantize to the 3 canonical occupancy-grid values ────────────
    ; Build a temporary indexed palette of exactly {0, 205, 254} and force
    ; every pixel to snap to its nearest entry — this both cleans up
    ; despeckle's soft edges AND guarantees map_server reads it correctly.
    (let* ((pal (car (gimp-palette-new "ros_map_cleanup_palette"))))
      (gimp-palette-add-entry pal "occupied" '(0 0 0))
      (gimp-palette-add-entry pal "unknown"  '(205 205 205))
      (gimp-palette-add-entry pal "free"     '(254 254 254))
      (gimp-image-convert-indexed image
                                   NO-DITHER
                                   CUSTOM-PALETTE
                                   3        ; num colors (ignored for custom)
                                   FALSE    ; alpha-dither
                                   FALSE    ; remove-unused
                                   "ros_map_cleanup_palette")))
    (gimp-image-convert-grayscale image)
    (gimp-image-flatten image)
    (set! drawable (car (gimp-image-get-active-drawable image)))

    ; ── 4. Save as raw PGM (P5) ─────────────────────────────────────────────
    (file-pnm-save RUN-NONINTERACTIVE image drawable outfile outfile 1)

    (gimp-image-delete image)))

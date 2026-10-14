-- The size of each hosted screen, so layout can be tuned against real ones
-- (DIN-149).
--
-- The dashboard fits itself to the browser window. Which windows the hosted
-- dashboards actually run in is not something the config or the brief records,
-- and a column on `families` would be the wrong shape: one family can have
-- several screens.
--
-- One row per family and size. A panel refreshes every few minutes; the app
-- only moves `last_seen_at` when it is more than an hour old, so the write is
-- not on the refresh cadence. The row goes with the family: `accounts.delete_family`
-- deletes the family, and this reference cascades.
--
-- Width and height are CSS pixels. `pixel_ratio` is `devicePixelRatio`, to
-- three decimal places. The same bounds are enforced in `parse_viewport`
-- before a row is offered, and again here so a caller cannot widen them.
-- `user_agent` is the browser's own description, clipped. The screen token
-- is not a column.

CREATE TABLE screen_sizes (
    family_id     UUID NOT NULL REFERENCES families (id) ON DELETE CASCADE,
    width         INTEGER NOT NULL CHECK (width BETWEEN 1 AND 10000),
    height        INTEGER NOT NULL CHECK (height BETWEEN 1 AND 10000),
    pixel_ratio   NUMERIC(4,3) NOT NULL CHECK (pixel_ratio BETWEEN 0.250 AND 8.000),
    user_agent    TEXT NOT NULL DEFAULT '' CHECK (length(user_agent) <= 300),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (family_id, width, height, pixel_ratio)
);

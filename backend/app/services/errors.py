# =============================================================================
# Copyright (c) 2026 ZombieTech LLC. All rights reserved.
#
# SPDX-License-Identifier: PolyForm-Strict-1.0.0
# See LICENSE in the project root for the full terms.
#
# Licensing inquiries: license@zombietech.biz
# =============================================================================
# ai: claude-opus-5-5 | 2026-09-29
"""Domain errors raised by services.

Services don't choose HTTP status codes; app.main maps these to responses.
Messages are written by the services themselves, so they're safe to show clients.
Leaf module (no project imports) so every service and app.main can use it.
"""


class NotFoundError(Exception):
    """A requested record doesn't exist."""


class ConflictError(Exception):
    """The request conflicts with existing data (e.g. a receipt imported twice)."""

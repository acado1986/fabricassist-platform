#!/usr/bin/env python3
"""Fail if the shared Expo app bypasses the typed REST-write registry."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "frontend/apps/client/src"
WRITE_FUNCTIONS = (
    "addImageApiV1ScansScanIdImagesPost",
    "addServiceEventApiV1GarmentsGarmentIdServiceEventsPost",
    "approveReviewApiV1ReviewsReviewIdApprovePost",
    "assignReviewApiV1ReviewsReviewIdAssignPost",
    "cancelRunApiV1RunsRunIdCancelPost",
    "completeUploadApiV1ScansScanIdUploadsCompletePost",
    "confirmIdentityCandidateApiV1GarmentsIdentityCandidatesScanIdConfirmPost",
    "confirmServiceEventApiV1ReviewsReviewIdServiceEventsPost",
    "correctReviewApiV1ReviewsReviewIdCorrectionsPost",
    "createScanApiV1ScansPost",
    "deleteGarmentApiV1GarmentsGarmentIdDelete",
    "deleteScanApiV1ScansScanIdDelete",
    "invalidateLatestProductLookupApiV1ScansScanIdProductLookupInvalidatePost",
    "loginApiV1AuthLoginPost",
    "logoutApiV1AuthLogoutPost",
    "postMessageApiV1ScansScanIdMessagesPost",
    "productLookupApiV1ScansScanIdProductLookupPost",
    "refreshApiV1AuthRefreshPost",
    "registerApiV1AuthRegisterPost",
    "rejectIdentityCandidateApiV1GarmentsIdentityCandidatesScanIdRejectPost",
    "removeImageApiV1ScansScanIdImagesImageIdDelete",
    "requestAnalysisApiV1ScansScanIdAnalysePost",
    "retryRunApiV1RunsRunIdRetryPost",
    "startRunApiV1ScansScanIdRunsPost",
    "submitFeedbackApiV1ScansScanIdFeedbackPost",
)
WRITE_FUNCTION_PATTERN = re.compile(r"\b(?:" + "|".join(WRITE_FUNCTIONS) + r")\b")


def main() -> int:
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.ts*"):
        if "/__tests__/" in str(path):
            continue
        text = path.read_text()
        if WRITE_FUNCTION_PATTERN.search(text):
            violations.append(str(path.relative_to(ROOT)))
    if violations:
        print("REST write bypass detected; use @fabricassist/api-client restWrites:", file=sys.stderr)
        print("\n".join(sorted(violations)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

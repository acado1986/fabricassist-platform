"""Public FabricAssist garment-analysis module boundary.

Routes and workers must import this package, not its internal port or workflow
modules. The package is intentionally inactive until the coordinated v2 cutover.
"""

from fabricassist.application.garment_analysis.commands import (
    AnalysisBranch,
    ReanalyzeAnalysisBranch,
    RecordAnalysisCorrection,
    RecordGarmentCleaningEvent,
    ResumeGarmentAnalysis,
    StartGarmentAnalysis,
)
from fabricassist.application.garment_analysis.orchestration import (
    AsyncioGarmentAnalysisWorkflow,
    GarmentAnalysisWorkflowPolicy,
)
from fabricassist.application.garment_analysis.ports import (
    BranchClaim,
    BranchCompletion,
    BranchInvocation,
    BranchState,
    BranchStateRepository,
    FinalizationRepository,
    GarmentAnalysisRequest,
    GarmentAnalysisWorkflow,
    GarmentInspectionRequest,
    GarmentVisionProvider,
    ImageAssetRepository,
    LabelExtractionRequest,
    ModelInvocation,
    ProviderImage,
    StainTreatmentRequest,
)
from fabricassist.application.garment_analysis.prompts.registry import PromptAsset, load_prompt
from fabricassist.application.garment_analysis.queries import (
    AnalysisProgress,
    AnalysisReference,
    BranchProgress,
    CleaningEvent,
    FabricAssistAnalysisResult,
    GetGarmentAnalysis,
)
from fabricassist.application.garment_analysis.service import (
    DefaultGarmentAnalysisService,
    GarmentAnalysisService,
)

__all__ = [
    "AnalysisBranch",
    "AsyncioGarmentAnalysisWorkflow",
    "AnalysisProgress",
    "AnalysisReference",
    "BranchClaim",
    "BranchCompletion",
    "BranchInvocation",
    "BranchProgress",
    "BranchState",
    "BranchStateRepository",
    "CleaningEvent",
    "DefaultGarmentAnalysisService",
    "FabricAssistAnalysisResult",
    "FinalizationRepository",
    "GarmentAnalysisService",
    "GarmentAnalysisWorkflowPolicy",
    "GetGarmentAnalysis",
    "GarmentInspectionRequest",
    "GarmentAnalysisRequest",
    "GarmentAnalysisWorkflow",
    "GarmentVisionProvider",
    "ImageAssetRepository",
    "LabelExtractionRequest",
    "ModelInvocation",
    "PromptAsset",
    "ProviderImage",
    "StainTreatmentRequest",
    "load_prompt",
    "RecordAnalysisCorrection",
    "RecordGarmentCleaningEvent",
    "ReanalyzeAnalysisBranch",
    "ResumeGarmentAnalysis",
    "StartGarmentAnalysis",
]

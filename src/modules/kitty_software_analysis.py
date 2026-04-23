
import os
import re
import sys


class KittySoftwareAnalysis:
    def __init__(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        try:
            from tests.scripts.software_analysis_module import SoftwareAnalysisModule

            self.analysis = SoftwareAnalysisModule()
        except ImportError:
            self.analysis = None

        try:
            from tests.scripts.performance_assessment import PerformanceAssessment

            self.perf = PerformanceAssessment()
        except ImportError:
            self.perf = None

        try:
            from tests.scripts.safety_compliant_testing import SafetyCompliantTesting

            self.safety = SafetyCompliantTesting()
        except ImportError:
            self.safety = None

    def process_request(self, request: str) -> dict:
        """Process a software analysis request."""
        if self.safety:
            is_safe, msg = self.safety.validate_test_scenario(request)
            if not is_safe:
                return {"status": "rejected", "reason": msg}

        if "analyze" in request.lower():
            file_path = self._extract_path(request)
            if not file_path or not os.path.exists(file_path):
                return {"status": "error", "message": "File not found"}

            atype = "protection" if "protect" in request.lower() else "structure"

            if self.analysis:
                result = self.analysis.analyze_binary(file_path, atype)
                return {"status": "completed", "result": result}

            return {"status": "error", "message": "Analysis module not available"}

        return {"status": "error", "message": "Unknown request"}

    def _extract_path(self, request: str) -> str | None:
        """Extract file path from request."""
        match = re.search(r"""['"]([^'"]+)['"]""", request)
        if match:
            return match.group(1)
        return None

    def get_capabilities(self) -> dict:
        """Get system capabilities."""
        return {
            "binary_analysis": self.analysis is not None,
            "performance_assessment": self.perf is not None,
            "safety_testing": self.safety is not None,
            "modules_loaded": bool(self.analysis and self.safety),
        }

    def run_assessment(self) -> dict:
        """Run performance assessment."""
        if self.perf:
            return self.perf.run_assessment()
        return {"status": "unavailable"}


def main():
    ksa = KittySoftwareAnalysis()
    caps = ksa.get_capabilities()
    print("\n=== Kitty Software Analysis ===")
    for k, v in caps.items():
        print(f"  {k}: {v}")
    return caps


if __name__ == "__main__":
    main()

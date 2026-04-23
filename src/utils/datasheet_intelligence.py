#!/usr/bin/env python3
"""
Datasheet Intelligence System for Kitty AI
Auto-fetches datasheets, extracts specs, and cross-references equivalent parts.

Integration sources:
- Octopart API (primary)
- AllDatasheets.com (backup)
- Manufacturer websites (direct fetch)
- PDF extraction using PyPDF2/pdfplumber
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Cache directory for downloaded datasheets
DATASHEET_CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "cache" / "datasheets"
DATASHEET_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ComponentSpecs:
    """Standardized component specifications extracted from datasheets."""

    part_number: str
    manufacturer: str | None = None
    description: str | None = None

    # Electrical specs
    voltage_rating: float | None = None  # V
    current_rating: float | None = None  # A
    power_rating: float | None = None  # W
    resistance: float | None = None  # Ohms
    capacitance: float | None = None  # Farads
    inductance: float | None = None  # Henries

    # Tolerances
    tolerance: str | None = None  # e.g., "±5%", "±10%"
    temp_coefficient: str | None = None  # e.g., "X7R", "NP0"

    # Package/Physical
    package: str | None = None  # e.g., "0603", "SOT-23", "TO-220"
    footprint: str | None = None
    mounting_type: str | None = None  # SMD, Through-hole

    # Temperature
    operating_temp_min: float | None = None  # °C
    operating_temp_max: float | None = None  # °C

    # Pinout (for ICs)
    pin_count: int | None = None
    pinout: dict[str, Any] | None = None

    # Source info
    datasheet_url: str | None = None
    datasheet_path: str | None = None
    extracted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComponentSpecs":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class DatasheetFetcher:
    """
    Fetches datasheets from multiple sources and extracts specifications.

    Usage:
        fetcher = DatasheetFetcher()

        # Fetch datasheet
        result = fetcher.fetch_datasheet("2N2222", "ON Semiconductor")

        # Extract specs
        specs = fetcher.extract_specs(result['pdf_path'])
    """

    def __init__(self, octopart_api_key: str | None = None, cache_dir: Path | None = None):
        self.octopart_api_key = octopart_api_key or os.getenv("OCTOPART_API_KEY")
        self.cache_dir = cache_dir or DATASHEET_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Source priorities
        self.sources = ["octopart", "alldatasheets", "manufacturer"]

    def fetch_datasheet(
        self,
        part_number: str,
        manufacturer: str | None = None,
        preferred_source: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch datasheet for a component from available sources.

        Args:
            part_number: Component part number (e.g., "2N2222", "LM358")
            manufacturer: Optional manufacturer name
            preferred_source: Preferred source ('octopart', 'alldatasheets', 'manufacturer')

        Returns:
            Dict with:
                - success: bool
                - pdf_path: Local path to downloaded PDF
                - url: Original datasheet URL
                - source: Which source was used
                - metadata: Additional info from source
        """
        part_number = self._normalize_part_number(part_number)
        cache_key = self._get_cache_key(part_number, manufacturer)

        # Check cache first
        cached = self._check_cache(cache_key)
        if cached:
            logger.info(f"Using cached datasheet for {part_number}")
            return cached

        sources_to_try = [preferred_source] if preferred_source else self.sources

        for source in sources_to_try:
            if not source:
                continue

            try:
                if source == "octopart" and self.octopart_api_key:
                    result = self._fetch_from_octopart(part_number, manufacturer)
                    if result.get("success"):
                        return result

                elif source == "alldatasheets":
                    result = self._fetch_from_alldatasheets(part_number, manufacturer)
                    if result.get("success"):
                        return result

                elif source == "manufacturer":
                    result = self._fetch_from_manufacturer(part_number, manufacturer)
                    if result.get("success"):
                        return result

            except Exception as e:
                logger.warning(f"Failed to fetch from {source}: {e}")
                continue

        return {
            "success": False,
            "error": f"Could not find datasheet for {part_number} from any source",
        }

    def extract_specs(self, pdf_path: str) -> ComponentSpecs:
        """
        Extract key specifications from a datasheet PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ComponentSpecs with extracted information
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Extract text from PDF
        text = self.parse_datasheet_text(pdf_path)

        # Parse specs from text
        specs = self._parse_specs_from_text(text)
        specs.datasheet_path = pdf_path
        specs.extracted_at = datetime.now().isoformat()

        return specs

    def parse_datasheet_text(self, pdf_path: str) -> str:
        """
        Extract text content from a PDF datasheet.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        text_parts = []

        # Try pdfplumber first (better for tables)
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            if text_parts:
                return "\n\n".join(text_parts)
        except ImportError:
            logger.debug("pdfplumber not available, trying PyPDF2")
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}")

        # Fallback to PyPDF2
        try:
            import PyPDF2

            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            return "\n\n".join(text_parts)
        except ImportError:
            logger.error("Neither pdfplumber nor PyPDF2 available")
            return ""
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            return ""

    def _fetch_from_octopart(
        self, part_number: str, manufacturer: str | None = None
    ) -> dict[str, Any]:
        """Fetch datasheet from Octopart API."""
        if not self.octopart_api_key:
            return {"success": False, "error": "No Octopart API key"}

        try:
            # Octopart API v4 endpoint
            url = "https://octopart.com/api/v4/parts/search"
            headers = {"Authorization": f"Token {self.octopart_api_key}"}

            query = part_number
            if manufacturer:
                query = f"{manufacturer} {part_number}"

            params = {"q": query, "limit": 5, "include": "datasheets,specs,manufacturer"}

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                return {"success": False, "error": "No results from Octopart"}

            # Find best match
            best_match = None
            for result in results:
                part = result.get("item", {})
                mpn = part.get("mpn", "").upper()
                if mpn == part_number.upper():
                    best_match = part
                    break

            if not best_match:
                best_match = results[0].get("item", {})

            # Get datasheet URL
            datasheets = best_match.get("datasheets", [])
            if not datasheets:
                return {"success": False, "error": "No datasheet in Octopart result"}

            datasheet_url = datasheets[0].get("url", "")
            if not datasheet_url:
                return {"success": False, "error": "Empty datasheet URL"}

            # Download PDF
            pdf_path = self._download_pdf(datasheet_url, part_number)

            if pdf_path:
                # Cache result
                cache_key = self._get_cache_key(part_number, manufacturer)
                result = {
                    "success": True,
                    "pdf_path": str(pdf_path),
                    "url": datasheet_url,
                    "source": "octopart",
                    "metadata": {
                        "manufacturer": best_match.get("manufacturer", {}).get("name"),
                        "mpn": best_match.get("mpn"),
                        "description": best_match.get("short_description"),
                        "specs": best_match.get("specs", {}),
                    },
                }
                self._save_to_cache(cache_key, result)
                return result
            else:
                return {"success": False, "error": "Failed to download PDF"}

        except requests.RequestException as e:
            logger.error(f"Octopart API error: {e}")
            return {"success": False, "error": f"Octopart API error: {e}"}
        except Exception as e:
            logger.error(f"Octopart fetch error: {e}")
            return {"success": False, "error": str(e)}

    def _fetch_from_alldatasheets(
        self, part_number: str, manufacturer: str | None = None
    ) -> dict[str, Any]:
        """Fetch datasheet from AllDatasheets.com."""
        try:
            # AllDatasheets search URL
            search_url = f"https://www.alldatasheet.com/datasheet-pdf/pdf/{quote(part_number)}.html"

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

            # Search for the part
            response = requests.get(search_url, headers=headers, timeout=30, allow_redirects=True)

            # If redirected to PDF, that's our datasheet
            if response.headers.get("content-type", "").startswith("application/pdf"):
                pdf_path = self._save_pdf_content(response.content, part_number)
                if pdf_path:
                    result = {
                        "success": True,
                        "pdf_path": str(pdf_path),
                        "url": response.url,
                        "source": "alldatasheets",
                        "metadata": {},
                    }
                    cache_key = self._get_cache_key(part_number, manufacturer)
                    self._save_to_cache(cache_key, result)
                    return result

            # Parse HTML to find PDF link
            html = response.text
            pdf_pattern = r'href="([^"]*\.pdf)"'
            pdf_matches = re.findall(pdf_pattern, html, re.IGNORECASE)

            for pdf_url in pdf_matches[:3]:  # Try first 3 PDF links
                if not pdf_url.startswith("http"):
                    pdf_url = "https://www.alldatasheet.com" + pdf_url

                try:
                    pdf_response = requests.get(pdf_url, headers=headers, timeout=30)
                    if pdf_response.headers.get("content-type", "").startswith("application/pdf"):
                        pdf_path = self._save_pdf_content(pdf_response.content, part_number)
                        if pdf_path:
                            result = {
                                "success": True,
                                "pdf_path": str(pdf_path),
                                "url": pdf_url,
                                "source": "alldatasheets",
                                "metadata": {},
                            }
                            cache_key = self._get_cache_key(part_number, manufacturer)
                            self._save_to_cache(cache_key, result)
                            return result
                except Exception as e:
                    logger.debug(f"Failed to download PDF from {pdf_url}: {e}")
                    continue

            return {"success": False, "error": "No PDF found on AllDatasheets"}

        except Exception as e:
            logger.error(f"AllDatasheets fetch error: {e}")
            return {"success": False, "error": str(e)}

    def _fetch_from_manufacturer(
        self, part_number: str, manufacturer: str | None = None
    ) -> dict[str, Any]:
        """
        Attempt to fetch datasheet directly from common manufacturer sites.
        """
        if not manufacturer:
            return {"success": False, "error": "Manufacturer required for direct fetch"}

        manufacturer_urls = self._get_manufacturer_urls(manufacturer, part_number)

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for url in manufacturer_urls:
            try:
                response = requests.get(url, headers=headers, timeout=30)

                if response.headers.get("content-type", "").startswith("application/pdf"):
                    pdf_path = self._save_pdf_content(response.content, part_number)
                    if pdf_path:
                        result = {
                            "success": True,
                            "pdf_path": str(pdf_path),
                            "url": url,
                            "source": "manufacturer",
                            "metadata": {"manufacturer": manufacturer},
                        }
                        cache_key = self._get_cache_key(part_number, manufacturer)
                        self._save_to_cache(cache_key, result)
                        return result

            except Exception as e:
                logger.debug(f"Failed to fetch from {url}: {e}")
                continue

        return {"success": False, "error": "Failed to fetch from manufacturer"}

    def _get_manufacturer_urls(self, manufacturer: str, part_number: str) -> list[str]:
        """Generate possible datasheet URLs for known manufacturers."""
        manufacturer = manufacturer.lower()
        urls = []

        # Common manufacturer URL patterns
        patterns = {
            "texas instruments": [
                f"https://www.ti.com/lit/ds/symlink/{part_number.lower()}.pdf",
                f"https://www.ti.com/lit/gpn/{part_number.lower()}",
            ],
            "ti": [
                f"https://www.ti.com/lit/ds/symlink/{part_number.lower()}.pdf",
            ],
            "analog devices": [
                f"https://www.analog.com/media/en/technical-documentation/data-sheets/{part_number}.pdf",
            ],
            "adi": [
                f"https://www.analog.com/media/en/technical-documentation/data-sheets/{part_number}.pdf",
            ],
            "on semiconductor": [
                f"https://www.onsemi.com/pdf/datasheet/{part_number}-d.pdf",
            ],
            "onsemi": [
                f"https://www.onsemi.com/pdf/datasheet/{part_number}-d.pdf",
            ],
            "stmicroelectronics": [
                f"https://www.st.com/resource/en/datasheet/{part_number.lower()}.pdf",
            ],
            "st": [
                f"https://www.st.com/resource/en/datasheet/{part_number.lower()}.pdf",
            ],
            "microchip": [
                f"https://ww1.microchip.com/downloads/en/DeviceDoc/{part_number}.pdf",
            ],
            "atmel": [
                f"https://ww1.microchip.com/downloads/en/DeviceDoc/{part_number}.pdf",
            ],
            "nxp": [
                f"https://www.nxp.com/docs/en/data-sheet/{part_number}.pdf",
            ],
            "infineon": [
                f"https://www.infineon.com/dgdl/{part_number}.pdf",
            ],
            "vishay": [
                f"https://www.vishay.com/docs/{part_number[:2].lower()}xxx/{part_number}.pdf",
            ],
            "murata": [
                f"https://www.murata.com/~/media/webrenewal/support/library/catalog/{part_number}.pdf",
            ],
            "samwha": [
                f"http://www.samwha.com/upload/{part_number}.pdf",
            ],
            "rubycon": [
                f"https://www.rubycon.co.jp/catalog/{part_number}-e.pdf",
            ],
            "nichicon": [
                f"https://www.nichicon.co.jp/english/products/pdfs/{part_number}.pdf",
            ],
            "panasonic": [
                f"https://industrial.panasonic.com/cdbs/www-data/pdf/{part_number[:2]}{part_number[2:4]}{part_number[4:6]}/{part_number}.pdf",
            ],
            "samsung": [
                f"https://www.samsungsem.com/resources/data-sheet/{part_number}.pdf",
            ],
            "taiyo yuden": [
                f"https://www.yuden.co.jp/productdata/en/{part_number}.pdf",
            ],
        }

        for key, pattern_urls in patterns.items():
            if key in manufacturer:
                urls.extend(pattern_urls)

        return urls

    def _parse_specs_from_text(self, text: str) -> ComponentSpecs:
        """Parse component specifications from datasheet text."""
        specs = ComponentSpecs(part_number="")

        # Extract part number
        mpn_match = re.search(r"(Part Number|MPN|Model)[\s:]+([A-Z0-9\-/]+)", text, re.IGNORECASE)
        if mpn_match:
            specs.part_number = mpn_match.group(2).strip()

        # Extract manufacturer
        mfg_match = re.search(r"(Manufacturer|Vendor)[\s:]+([A-Za-z0-9\s]+)", text, re.IGNORECASE)
        if mfg_match:
            specs.manufacturer = mfg_match.group(2).strip()

        # Extract voltage rating
        voltage_patterns = [
            r"(\d+\.?\d*)\s*[Vv][\s,]*(rating|max|maximum)",
            r"(rating|max|maximum)[\s:]+(\d+\.?\d*)\s*[Vv]",
            r"(\d+\.?\d*)[Vv](?:\s|,|$)",  # Standalone voltage
        ]
        for pattern in voltage_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    specs.voltage_rating = float(
                        match.group(1) if match.lastindex == 1 else match.group(2)
                    )
                    break
                except (ValueError, IndexError):
                    continue

        # Extract current rating
        current_patterns = [
            r"(\d+\.?\d*)\s*[mM]?[aA][\s,]*(rating|max|maximum)",
            r"(rating|max|maximum)[\s:]+(\d+\.?\d*)\s*[mM]?[aA]",
            r"(\d+\.?\d*)\s*A(?:\s|,|$)",
            r"(\d+\.?\d*)\s*mA(?:\s|,|$)",
        ]
        for pattern in current_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1) if match.lastindex == 1 else match.group(2))
                    # Convert mA to A if pattern matches mA
                    if "mA" in pattern and "mA" in match.group(0):
                        value = value / 1000
                    specs.current_rating = value
                    break
                except (ValueError, IndexError):
                    continue

        # Extract power rating
        power_patterns = [
            r"(\d+\.?\d*)\s*[Ww][\s,]*(rating|max|maximum|dissipation)",
            r"(\d+\.?\d*)\s*[mM]?[Ww](?:\s|,|$)",
        ]
        for pattern in power_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if "mW" in match.group(0):
                        value = value / 1000
                    specs.power_rating = value
                    break
                except (ValueError, IndexError):
                    continue

        # Extract resistance
        resistance_patterns = [
            r"(\d+\.?\d*)\s*[Ωohm]+",
            r"(\d+\.?\d*)\s*[kK][Ωohm]*",
            r"(\d+\.?\d*)\s*[mM][Ωohm]*",
        ]
        for pattern in resistance_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if "k" in match.group(0).lower():
                        value = value * 1000
                    elif "m" in match.group(0).lower() and "m" in match.group(0)[-5:].lower():
                        value = value * 1000000
                    specs.resistance = value
                    break
                except (ValueError, IndexError):
                    continue

        # Extract capacitance
        capacitance_patterns = [
            r"(\d+\.?\d*)\s*[pP][Ff]",
            r"(\d+\.?\d*)\s*[nN][Ff]",
            r"(\d+\.?\d*)\s*[uUµ][Ff]",
            r"(\d+\.?\d*)\s*[mM][Ff]",
        ]
        for pattern in capacitance_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    value = float(match.group(1))
                    if "pF" in pattern or "p" in match.group(0)[-4:].lower():
                        value = value * 1e-12
                    elif "nF" in pattern or "n" in match.group(0)[-4:].lower():
                        value = value * 1e-9
                    elif "uF" in pattern or "µF" in pattern or "u" in match.group(0)[-4:].lower():
                        value = value * 1e-6
                    elif "mF" in pattern or "m" in match.group(0)[-4:].lower():
                        value = value * 1e-3
                    specs.capacitance = value
                    break
                except (ValueError, IndexError):
                    continue

        # Extract tolerance
        tolerance_match = re.search(r"[tT]olerance[\s:]+[±+\-]?\s*(\d+\.?\d*)\s*%", text)
        if tolerance_match:
            specs.tolerance = f"±{tolerance_match.group(1)}%"
        else:
            # Look for tolerance codes
            tolerance_codes = re.search(r"[tT]olerance[\s:]+([A-Z]|±\d+%|\+\d+/-\d+%)", text)
            if tolerance_codes:
                specs.tolerance = tolerance_codes.group(1)

        # Extract package
        package_patterns = [
            r"([0-9]{4})\s+(package|case|size)",  # 0603, 0805, etc.
            r"(SOT-?\d+|TO-?\d+|DIP-?\d+|SOIC-?\d+|QFN-?\d+|TQFP-?\d+)",
            r"([0-9]{4})\s*mm",
        ]
        for pattern in package_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                specs.package = match.group(1).upper()
                break

        # Extract operating temperature
        temp_match = re.search(
            r"[oO]perating\s+[tT]emp[\s:]+(-?\d+)\s*°?[Cc]\s*[/to\-]+\s*\+?(\d+)\s*°?[Cc]", text
        )
        if temp_match:
            try:
                specs.operating_temp_min = float(temp_match.group(1))
                specs.operating_temp_max = float(temp_match.group(2))
            except (ValueError, IndexError):
                pass

        # Extract pin count
        pin_match = re.search(r"(\d+)[\s\-]*[pP]in", text)
        if pin_match:
            try:
                specs.pin_count = int(pin_match.group(1))
            except ValueError:
                pass

        return specs

    def _download_pdf(self, url: str, part_number: str) -> Path | None:
        """Download PDF from URL and save to cache."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()

            if not response.headers.get("content-type", "").startswith("application/pdf"):
                logger.warning(f"URL did not return PDF content-type: {url}")
                # Try anyway, some servers misconfigure headers

            return self._save_pdf_content(response.content, part_number)

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            return None

    def _save_pdf_content(self, content: bytes, part_number: str) -> Path | None:
        """Save PDF content to cache directory."""
        try:
            safe_name = re.sub(r"[^\w\-_.]", "_", part_number)
            pdf_path = self.cache_dir / f"{safe_name}.pdf"

            with open(pdf_path, "wb") as f:
                f.write(content)

            logger.info(f"Saved PDF: {pdf_path} ({len(content)} bytes)")
            return pdf_path

        except Exception as e:
            logger.error(f"Failed to save PDF: {e}")
            return None

    def _get_cache_key(self, part_number: str, manufacturer: str | None) -> str:
        """Generate cache key for a component."""
        key = part_number.upper()
        if manufacturer:
            key = f"{manufacturer.upper()}_{key}"
        return hashlib.md5(key.encode()).hexdigest()

    def _check_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Check if datasheet is already cached."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        pdf_file = self.cache_dir / f"{cache_key}.pdf"

        if cache_file.exists() and pdf_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        return None

    def _save_to_cache(self, cache_key: str, result: dict[str, Any]):
        """Save datasheet result to cache."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _normalize_part_number(self, part_number: str) -> str:
        """Normalize part number for searching."""
        # Remove common suffixes that don't affect the datasheet
        part_number = part_number.strip().upper()

        # Remove packaging/grade suffixes (keep base part)
        suffixes_to_remove = [
            r"-TR$",
            r"-T$",
            r"-ND$",
            r"CT-ND$",
            r"-REEL$",
            r"-[A-Z]$",  # Temperature grade
            r"-[0-9]+$",  # Packaging codes
        ]

        for suffix in suffixes_to_remove:
            part_number = re.sub(suffix, "", part_number)

        return part_number


class CrossReferenceEngine:
    """
    Find equivalent parts and check compatibility between components.

    Usage:
        xref = CrossReferenceEngine()

        # Find drop-in replacements
        equivalents = xref.find_equivalent_parts("2N2222")

        # Check compatibility
        is_compatible = xref.check_compatibility("2N2222", "PN2222")

        # Get substitutions with priority
        subs = xref.get_substitutions("LM358", priority='cost')
    """

    def __init__(self, octopart_api_key: str | None = None):
        self.octopart_api_key = octopart_api_key or os.getenv("OCTOPART_API_KEY")

        # Known cross-reference database (built-in common equivalents)
        self._common_equivalents = self._load_common_equivalents()

    def find_equivalent_parts(
        self, part_number: str, manufacturer: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Find drop-in replacement parts for a given component.

        Args:
            part_number: Original part number
            manufacturer: Optional original manufacturer
            limit: Maximum number of results

        Returns:
            List of equivalent parts with compatibility info
        """
        part_number = part_number.upper().strip()
        equivalents = []

        # Check built-in database first
        if part_number in self._common_equivalents:
            for equiv in self._common_equivalents[part_number]:
                equivalents.append(
                    {
                        "part_number": equiv["pn"],
                        "manufacturer": equiv.get("mfg", "Various"),
                        "type": equiv.get("type", "direct"),
                        "confidence": equiv.get("confidence", 0.95),
                        "notes": equiv.get("notes", ""),
                    }
                )

        # Search Octopart for additional equivalents
        if self.octopart_api_key:
            try:
                octopart_results = self._search_octopart_equivalents(
                    part_number, manufacturer, limit
                )
                equivalents.extend(octopart_results)
            except Exception as e:
                logger.warning(f"Octopart equivalent search failed: {e}")

        # Remove duplicates and sort by confidence
        seen = set()
        unique_equivalents = []
        for eq in equivalents:
            key = eq["part_number"].upper()
            if key not in seen and key != part_number:
                seen.add(key)
                unique_equivalents.append(eq)

        unique_equivalents.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        return unique_equivalents[:limit]

    def check_compatibility(self, part1: str, part2: str) -> dict[str, Any]:
        """
        Check if two parts are compatible (drop-in replacements).

        Args:
            part1: First part number
            part2: Second part number

        Returns:
            Dict with compatibility assessment
        """
        part1 = part1.upper().strip()
        part2 = part2.upper().strip()

        if part1 == part2:
            return {
                "compatible": True,
                "confidence": 1.0,
                "type": "identical",
                "notes": "Same part number",
            }

        # Check if they're in each other's equivalent lists
        p1_equivs = self.find_equivalent_parts(part1, limit=50)
        p2_equivs = self.find_equivalent_parts(part2, limit=50)

        p1_equiv_pns = [e["part_number"].upper() for e in p1_equivs]
        p2_equiv_pns = [e["part_number"].upper() for e in p2_equivs]

        if part2 in p1_equiv_pns or part1 in p2_equiv_pns:
            return {
                "compatible": True,
                "confidence": 0.9,
                "type": "direct_replacement",
                "notes": "Known cross-reference",
            }

        # Check prefix matching (same family)
        p1_base = re.sub(r"[0-9].*$", "", part1)
        p2_base = re.sub(r"[0-9].*$", "", part2)

        if p1_base == p2_base:
            return {
                "compatible": False,
                "confidence": 0.5,
                "type": "same_family",
                "notes": f"Same family ({p1_base}) but different specs - verify compatibility",
            }

        return {
            "compatible": False,
            "confidence": 0.2,
            "type": "unknown",
            "notes": "No known compatibility relationship",
        }

    def get_substitutions(
        self, part_number: str, priority: str = "cost", manufacturer: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get substitution recommendations with priority.

        Args:
            part_number: Original part number
            priority: 'cost', 'availability', or 'specs'
            manufacturer: Optional original manufacturer

        Returns:
            List of substitution options sorted by priority
        """
        equivalents = self.find_equivalent_parts(part_number, manufacturer, limit=20)

        if priority == "cost":
            # Sort by estimated cost (lower is better)
            # In real implementation, would have actual pricing data
            for eq in equivalents:
                # Heuristic: common parts are cheaper
                eq["priority_score"] = eq.get("confidence", 0.5) * 0.7 + 0.3

        elif priority == "availability":
            # Sort by availability score
            for eq in equivalents:
                # Heuristic: parts from major manufacturers more available
                major_mfgs = ["TI", "ON", "ST", "NXP", "MICROCHIP", "VISHAY", "MURATA"]
                mfg = eq.get("manufacturer", "").upper()
                availability_bonus = 0.3 if any(mm in mfg for mm in major_mfgs) else 0
                eq["priority_score"] = eq.get("confidence", 0.5) + availability_bonus

        elif priority == "specs":
            # Sort by spec match confidence
            for eq in equivalents:
                eq["priority_score"] = eq.get("confidence", 0.5)

        # Sort by priority score
        equivalents.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

        return equivalents

    def _search_octopart_equivalents(
        self, part_number: str, manufacturer: str | None, limit: int
    ) -> list[dict[str, Any]]:
        """Search Octopart for equivalent parts."""
        if not self.octopart_api_key:
            return []

        try:
            url = "https://octopart.com/api/v4/parts/search"
            headers = {"Authorization": f"Token {self.octopart_api_key}"}

            # Search for similar parts
            params = {
                "q": part_number,
                "limit": limit * 2,  # Get more to filter
                "include": "specs,manufacturer",
            }

            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for result in data.get("results", []):
                part = result.get("item", {})
                mpn = part.get("mpn", "")

                # Skip exact match
                if mpn.upper() == part_number.upper():
                    continue

                # Calculate similarity score
                confidence = self._calculate_similarity(part_number, mpn, part)

                if confidence > 0.6:  # Only include reasonably similar parts
                    results.append(
                        {
                            "part_number": mpn,
                            "manufacturer": part.get("manufacturer", {}).get("name", "Unknown"),
                            "type": "octopart_match",
                            "confidence": confidence,
                            "notes": part.get("short_description", ""),
                        }
                    )

            return results

        except Exception as e:
            logger.error(f"Octopart equivalent search error: {e}")
            return []

    def _calculate_similarity(
        self, original: str, candidate: str, part_data: dict[str, Any]
    ) -> float:
        """Calculate similarity score between original and candidate part."""
        original = original.upper()
        candidate = candidate.upper()

        # Exact family match
        if original.rstrip("0123456789") == candidate.rstrip("0123456789"):
            return 0.95

        # Similar naming pattern
        orig_prefix = re.sub(r"[0-9].*$", "", original)
        cand_prefix = re.sub(r"[0-9].*$", "", candidate)

        if orig_prefix == cand_prefix:
            return 0.8

        # Check specs similarity if available
        specs = part_data.get("specs", {})
        if specs:
            return 0.7  # Specs available, likely similar

        # Basic string similarity
        import difflib

        return difflib.SequenceMatcher(None, original, candidate).ratio()

    def _load_common_equivalents(self) -> dict[str, list[dict[str, Any]]]:
        """Load built-in cross-reference database."""
        return {
            # Common transistors
            "2N2222": [
                {
                    "pn": "PN2222",
                    "mfg": "ON Semiconductor",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Pin-compatible NPN transistor",
                },
                {
                    "pn": "2N2222A",
                    "mfg": "Various",
                    "type": "direct",
                    "confidence": 0.98,
                    "notes": "Higher voltage rating",
                },
                {
                    "pn": "2N3904",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "Similar NPN, lower current",
                },
                {
                    "pn": "BC547",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.80,
                    "notes": "European equivalent",
                },
            ],
            "2N2907": [
                {
                    "pn": "PN2907",
                    "mfg": "ON Semiconductor",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Pin-compatible PNP transistor",
                },
                {
                    "pn": "2N3906",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "Similar PNP",
                },
            ],
            "2N3904": [
                {
                    "pn": "2N2222",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "Higher current NPN",
                },
                {
                    "pn": "BC547",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "European equivalent",
                },
            ],
            "2N3906": [
                {
                    "pn": "2N2907",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "Higher current PNP",
                },
                {
                    "pn": "BC557",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.85,
                    "notes": "European equivalent",
                },
            ],
            # Common op-amps
            "LM358": [
                {
                    "pn": "LM358N",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Same part, DIP package",
                },
                {
                    "pn": "LM358D",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Same part, SOIC package",
                },
                {
                    "pn": "LM2904",
                    "mfg": "TI",
                    "type": "functional",
                    "confidence": 0.90,
                    "notes": "Industrial temp range",
                },
                {
                    "pn": "NE5532",
                    "mfg": "TI",
                    "type": "functional",
                    "confidence": 0.75,
                    "notes": "Lower noise, higher bandwidth",
                },
            ],
            "LM741": [
                {
                    "pn": "LM741C",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Commercial grade",
                },
                {
                    "pn": "LM741CN",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "DIP package",
                },
                {
                    "pn": "TL071",
                    "mfg": "TI",
                    "type": "functional",
                    "confidence": 0.80,
                    "notes": "FET input, better specs",
                },
                {
                    "pn": "OP07",
                    "mfg": "Analog Devices",
                    "type": "functional",
                    "confidence": 0.80,
                    "notes": "Precision version",
                },
            ],
            # Common regulators
            "LM7805": [
                {
                    "pn": "LM7805CT",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Same part, TO-220",
                },
                {
                    "pn": "LM340T-5.0",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "Original part number",
                },
                {
                    "pn": "7805",
                    "mfg": "Various",
                    "type": "direct",
                    "confidence": 0.95,
                    "notes": "Generic 7805",
                },
                {
                    "pn": "L7805CV",
                    "mfg": "ST",
                    "type": "direct",
                    "confidence": 0.95,
                    "notes": "ST version",
                },
            ],
            "LM317": [
                {
                    "pn": "LM317T",
                    "mfg": "TI",
                    "type": "direct",
                    "confidence": 0.99,
                    "notes": "TO-220 package",
                },
                {
                    "pn": "LM317L",
                    "mfg": "TI",
                    "type": "functional",
                    "confidence": 0.90,
                    "notes": "Lower current version",
                },
                {
                    "pn": "LM337",
                    "mfg": "TI",
                    "type": "functional",
                    "confidence": 0.70,
                    "notes": "Negative voltage version",
                },
            ],
            # Common diodes
            "1N4001": [
                {
                    "pn": "1N4002",
                    "mfg": "Various",
                    "type": "upgrade",
                    "confidence": 0.95,
                    "notes": "Higher voltage rating (100V)",
                },
                {
                    "pn": "1N4003",
                    "mfg": "Various",
                    "type": "upgrade",
                    "confidence": 0.95,
                    "notes": "Higher voltage rating (200V)",
                },
                {
                    "pn": "1N4004",
                    "mfg": "Various",
                    "type": "upgrade",
                    "confidence": 0.95,
                    "notes": "Higher voltage rating (400V)",
                },
                {
                    "pn": "1N4007",
                    "mfg": "Various",
                    "type": "upgrade",
                    "confidence": 0.95,
                    "notes": "Highest voltage rating (1000V)",
                },
            ],
            "1N4148": [
                {
                    "pn": "1N914",
                    "mfg": "Various",
                    "type": "direct",
                    "confidence": 0.95,
                    "notes": "Original part number",
                },
                {
                    "pn": "1N4448",
                    "mfg": "Various",
                    "type": "functional",
                    "confidence": 0.90,
                    "notes": "Similar switching diode",
                },
            ],
            # Common LEDs
            "5MM_RED_LED": [
                {
                    "pn": "WP710A10ID",
                    "mfg": "Kingbright",
                    "type": "direct",
                    "confidence": 0.95,
                    "notes": "5mm red LED",
                },
                {
                    "pn": "L-53SRD-D",
                    "mfg": "Kingbright",
                    "type": "direct",
                    "confidence": 0.95,
                    "notes": "5mm red LED",
                },
            ],
        }


# Convenience functions for quick access
def fetch_datasheet(part_number: str, manufacturer: str | None = None) -> dict[str, Any]:
    """Quick function to fetch a datasheet."""
    fetcher = DatasheetFetcher()
    return fetcher.fetch_datasheet(part_number, manufacturer)


def find_equivalents(part_number: str, limit: int = 10) -> list[dict[str, Any]]:
    """Quick function to find equivalent parts."""
    xref = CrossReferenceEngine()
    return xref.find_equivalent_parts(part_number, limit=limit)


def extract_specs_from_datasheet(pdf_path: str) -> ComponentSpecs:
    """Quick function to extract specs from a PDF."""
    fetcher = DatasheetFetcher()
    return fetcher.extract_specs(pdf_path)


if __name__ == "__main__":
    # Simple test
    logging.basicConfig(level=logging.INFO)

    print("Datasheet Intelligence System - Test")
    print("=" * 50)

    # Test cross-reference
    xref = CrossReferenceEngine()
    print("\nEquivalent parts for 2N2222:")
    for eq in xref.find_equivalent_parts("2N2222", limit=5):
        print(f"  - {eq['part_number']} ({eq['manufacturer']}): {eq['notes']}")

    # Test compatibility check
    print("\nCompatibility check (2N2222 vs PN2222):")
    result = xref.check_compatibility("2N2222", "PN2222")
    print(f"  Compatible: {result['compatible']}, Confidence: {result['confidence']}")
    print(f"  Notes: {result['notes']}")

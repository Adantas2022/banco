"""Loader para download de leiautes oficiais da Receita Federal.

Este módulo permite baixar automaticamente os leiautes técnicos
da DIRPF (Declaração de Imposto de Renda de Pessoa Física) diretamente
do site oficial da Receita Federal.

Uso:
    loader = LayoutLoader()
    results = loader.sync_all()
    
    for result in results:
        print(f"{result.year}: {result.status}")
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


class DownloadStatus(str, Enum):
    DOWNLOADED = "downloaded"
    ALREADY_EXISTS = "already_exists"
    UPDATED = "updated"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class LayoutInfo:
    """Informações sobre um leiaute da Receita Federal."""
    
    year: str
    title: str
    url: str
    filename: str
    file_size: int = 0
    checksum: str = ""
    downloaded_at: Optional[str] = None
    last_checked: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "LayoutInfo":
        return cls(**data)


@dataclass
class DownloadResult:
    """Resultado de uma operação de download."""
    
    year: str
    status: DownloadStatus
    message: str
    layout_info: Optional[LayoutInfo] = None
    error: Optional[str] = None


class LayoutLoader:
    """Loader para baixar leiautes oficiais da Receita Federal.
    
    Attributes:
        base_url: URL base da página de documentos técnicos da DIRPF
        download_path: Caminho local para salvar os leiautes
        cache_file: Arquivo JSON com metadados dos downloads
    """
    
    BASE_URL = "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf"
    
    KNOWN_LAYOUTS = {
        "2025": "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf/leiaute-dirpf-2025.pdf",
        "2024": "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf/leiaute-dirpf-2024.pdf",
        "2023": "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf/leiaute-dirpf-2023.pdf",
        "2022": "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf/leiaute-dirpf-2022.pdf",
        "2021": "https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/dirpf/leiaute-dirpf-2021.pdf",
    }
    
    def __init__(
        self,
        download_path: Optional[Path] = None,
        timeout: float = 30.0,
    ):
        if download_path is None:
            download_path = Path(__file__).parent.parent.parent / "data" / "receita_federal" / "leiautes"
        
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.download_path / "metadata.json"
        self.timeout = timeout
        self._cache: dict[str, LayoutInfo] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Carrega metadados do cache local."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for year, info in data.items():
                        self._cache[year] = LayoutInfo.from_dict(info)
                logger.info("Cache loaded", entries=len(self._cache))
            except Exception as e:
                logger.warning("Failed to load cache", error=str(e))
                self._cache = {}
    
    def _save_cache(self) -> None:
        """Salva metadados no cache local."""
        try:
            data = {year: info.to_dict() for year, info in self._cache.items()}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Cache saved", entries=len(self._cache))
        except Exception as e:
            logger.error("Failed to save cache", error=str(e))
    
    def _calculate_checksum(self, content: bytes) -> str:
        """Calcula SHA256 do conteúdo."""
        return hashlib.sha256(content).hexdigest()
    
    def _extract_year_from_text(self, text: str) -> Optional[str]:
        """Extrai ano do texto do link."""
        match = re.search(r"20[0-9]{2}", text)
        return match.group(0) if match else None
    
    def _extract_year_from_url(self, url: str) -> Optional[str]:
        """Extrai ano da URL."""
        match = re.search(r"dirpf[_-]?(20[0-9]{2})", url.lower())
        return match.group(1) if match else None
    
    def discover_layouts(self) -> list[LayoutInfo]:
        """Descobre leiautes disponíveis na página da Receita Federal.
        
        Returns:
            Lista de LayoutInfo com os leiautes encontrados
        """
        logger.info("Discovering layouts from Receita Federal", url=self.BASE_URL)
        layouts = []
        
        for year, url in self.KNOWN_LAYOUTS.items():
            layouts.append(LayoutInfo(
                year=year,
                title=f"Leiaute DIRPF {year}",
                url=url,
                filename=f"leiaute_dirpf_{year}.pdf",
            ))
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(self.BASE_URL)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                for link in soup.find_all("a", href=True):
                    href = link.get("href", "")
                    text = link.get_text(strip=True)
                    
                    if not href.endswith(".pdf"):
                        continue
                    
                    if "leiaute" not in text.lower() and "leiaute" not in href.lower():
                        continue
                    
                    if "dirpf" not in text.lower() and "dirpf" not in href.lower():
                        continue
                    
                    year = self._extract_year_from_url(href) or self._extract_year_from_text(text)
                    if not year:
                        continue
                    
                    if any(l.year == year for l in layouts):
                        continue
                    
                    full_url = href if href.startswith("http") else urljoin(self.BASE_URL, href)
                    
                    layouts.append(LayoutInfo(
                        year=year,
                        title=text or f"Leiaute DIRPF {year}",
                        url=full_url,
                        filename=f"leiaute_dirpf_{year}.pdf",
                    ))
                    
                    logger.info("Discovered new layout", year=year, url=full_url)
        
        except Exception as e:
            logger.warning("Failed to discover layouts from page, using known list", error=str(e))
        
        layouts.sort(key=lambda x: x.year, reverse=True)
        logger.info("Layouts discovered", count=len(layouts))
        return layouts
    
    def download_layout(self, layout: LayoutInfo, force: bool = False) -> DownloadResult:
        """Baixa um leiaute específico.
        
        Args:
            layout: Informações do leiaute a baixar
            force: Se True, baixa mesmo se já existir
            
        Returns:
            DownloadResult com o status da operação
        """
        file_path = self.download_path / layout.filename
        
        if file_path.exists() and not force:
            cached = self._cache.get(layout.year)
            if cached and cached.checksum:
                logger.debug("Layout already exists", year=layout.year)
                return DownloadResult(
                    year=layout.year,
                    status=DownloadStatus.ALREADY_EXISTS,
                    message=f"Leiaute {layout.year} já existe",
                    layout_info=cached,
                )
        
        logger.info("Downloading layout", year=layout.year, url=layout.url)
        
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(layout.url)
                response.raise_for_status()
                content = response.content
                
                checksum = self._calculate_checksum(content)
                
                cached = self._cache.get(layout.year)
                if cached and cached.checksum == checksum and file_path.exists():
                    layout.last_checked = datetime.utcnow().isoformat()
                    self._cache[layout.year] = layout
                    self._save_cache()
                    
                    return DownloadResult(
                        year=layout.year,
                        status=DownloadStatus.ALREADY_EXISTS,
                        message=f"Leiaute {layout.year} não mudou",
                        layout_info=layout,
                    )
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                layout.file_size = len(content)
                layout.checksum = checksum
                layout.downloaded_at = datetime.utcnow().isoformat()
                layout.last_checked = layout.downloaded_at
                
                self._cache[layout.year] = layout
                self._save_cache()
                
                status = DownloadStatus.UPDATED if cached else DownloadStatus.DOWNLOADED
                logger.info(
                    "Layout downloaded",
                    year=layout.year,
                    size=layout.file_size,
                    status=status.value,
                )
                
                return DownloadResult(
                    year=layout.year,
                    status=status,
                    message=f"Leiaute {layout.year} baixado com sucesso",
                    layout_info=layout,
                )
        
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error downloading layout", year=layout.year, status=e.response.status_code)
            return DownloadResult(
                year=layout.year,
                status=DownloadStatus.FAILED,
                message=f"Erro HTTP: {e.response.status_code}",
                error=str(e),
            )
        
        except Exception as e:
            logger.error("Error downloading layout", year=layout.year, error=str(e))
            return DownloadResult(
                year=layout.year,
                status=DownloadStatus.FAILED,
                message=f"Erro ao baixar: {str(e)}",
                error=str(e),
            )
    
    def sync_all(self, force: bool = False) -> list[DownloadResult]:
        """Sincroniza todos os leiautes disponíveis.
        
        Args:
            force: Se True, baixa novamente mesmo se já existir
            
        Returns:
            Lista de DownloadResult com o status de cada operação
        """
        layouts = self.discover_layouts()
        results = []
        
        for layout in layouts:
            result = self.download_layout(layout, force=force)
            results.append(result)
        
        downloaded = sum(1 for r in results if r.status == DownloadStatus.DOWNLOADED)
        updated = sum(1 for r in results if r.status == DownloadStatus.UPDATED)
        existing = sum(1 for r in results if r.status == DownloadStatus.ALREADY_EXISTS)
        failed = sum(1 for r in results if r.status == DownloadStatus.FAILED)
        
        logger.info(
            "Sync completed",
            downloaded=downloaded,
            updated=updated,
            existing=existing,
            failed=failed,
        )
        
        return results
    
    def sync_year(self, year: str, force: bool = False) -> DownloadResult:
        """Sincroniza leiaute de um ano específico.
        
        Args:
            year: Ano do exercício (ex: "2025")
            force: Se True, baixa novamente mesmo se já existir
            
        Returns:
            DownloadResult com o status da operação
        """
        if year in self.KNOWN_LAYOUTS:
            layout = LayoutInfo(
                year=year,
                title=f"Leiaute DIRPF {year}",
                url=self.KNOWN_LAYOUTS[year],
                filename=f"leiaute_dirpf_{year}.pdf",
            )
            return self.download_layout(layout, force=force)
        
        layouts = self.discover_layouts()
        for layout in layouts:
            if layout.year == year:
                return self.download_layout(layout, force=force)
        
        return DownloadResult(
            year=year,
            status=DownloadStatus.FAILED,
            message=f"Leiaute {year} não encontrado",
        )
    
    def get_cached_layouts(self) -> list[LayoutInfo]:
        """Retorna lista de leiautes em cache."""
        return list(self._cache.values())
    
    def get_layout_path(self, year: str) -> Optional[Path]:
        """Retorna caminho do arquivo de leiaute para um ano."""
        if year in self._cache:
            path = self.download_path / self._cache[year].filename
            if path.exists():
                return path
        return None
    
    def list_downloaded(self) -> list[str]:
        """Lista anos dos leiautes baixados."""
        return sorted(
            [f.stem.replace("leiaute_dirpf_", "") for f in self.download_path.glob("leiaute_dirpf_*.pdf")],
            reverse=True,
        )

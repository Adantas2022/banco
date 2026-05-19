#!/usr/bin/env python
"""CLI para sincronizar leiautes da Receita Federal.

Uso:
    python -m irpf_processor.cli.sync_layouts
    python -m irpf_processor.cli.sync_layouts --year 2025
    python -m irpf_processor.cli.sync_layouts --force
    python -m irpf_processor.cli.sync_layouts --list
"""

import argparse
import sys
from pathlib import Path

from irpf_processor.infrastructure.receita_federal import (
    LayoutLoader,
    DownloadResult,
)
from irpf_processor.infrastructure.receita_federal.layout_loader import DownloadStatus


def print_header():
    print()
    print("=" * 60)
    print("  📄 IRPF Processor - Sincronização de Leiautes")
    print("  🏛️  Fonte: Receita Federal do Brasil")
    print("=" * 60)
    print()


def print_result(result: DownloadResult):
    status_icons = {
        DownloadStatus.DOWNLOADED: "✅",
        DownloadStatus.UPDATED: "🔄",
        DownloadStatus.ALREADY_EXISTS: "📁",
        DownloadStatus.FAILED: "❌",
        DownloadStatus.SKIPPED: "⏭️",
    }
    
    icon = status_icons.get(result.status, "❓")
    print(f"  {icon} {result.year}: {result.message}")
    
    if result.layout_info and result.status in (DownloadStatus.DOWNLOADED, DownloadStatus.UPDATED):
        size_kb = result.layout_info.file_size / 1024
        print(f"      📦 Tamanho: {size_kb:.1f} KB")


def cmd_sync(args):
    print_header()
    
    loader = LayoutLoader()
    
    if args.year:
        print(f"📥 Sincronizando leiaute do ano {args.year}...")
        print()
        result = loader.sync_year(args.year, force=args.force)
        print_result(result)
    else:
        print("📥 Sincronizando todos os leiautes disponíveis...")
        print()
        results = loader.sync_all(force=args.force)
        
        for result in results:
            print_result(result)
        
        print()
        print("-" * 60)
        downloaded = sum(1 for r in results if r.status == DownloadStatus.DOWNLOADED)
        updated = sum(1 for r in results if r.status == DownloadStatus.UPDATED)
        existing = sum(1 for r in results if r.status == DownloadStatus.ALREADY_EXISTS)
        failed = sum(1 for r in results if r.status == DownloadStatus.FAILED)
        
        print(f"  📊 Resumo:")
        print(f"      ✅ Novos:      {downloaded}")
        print(f"      🔄 Atualizados: {updated}")
        print(f"      📁 Existentes: {existing}")
        print(f"      ❌ Falhas:     {failed}")
    
    print()
    print(f"📂 Diretório: {loader.download_path}")
    print()


def cmd_list(args):
    print_header()
    
    loader = LayoutLoader()
    
    print("📋 Leiautes disponíveis no cache:")
    print()
    
    cached = loader.get_cached_layouts()
    if not cached:
        print("  (nenhum leiaute baixado)")
        print()
        print("  Execute: python -m irpf_processor.cli.sync_layouts")
        print()
        return
    
    for layout in sorted(cached, key=lambda x: x.year, reverse=True):
        path = loader.get_layout_path(layout.year)
        exists = "✅" if path and path.exists() else "❌"
        size_kb = layout.file_size / 1024 if layout.file_size else 0
        
        print(f"  {exists} {layout.year}: {layout.title}")
        print(f"      📦 Tamanho: {size_kb:.1f} KB")
        print(f"      🔗 URL: {layout.url[:50]}...")
        if layout.downloaded_at:
            print(f"      📅 Baixado: {layout.downloaded_at[:10]}")
        print()
    
    print(f"📂 Diretório: {loader.download_path}")
    print()


def cmd_discover(args):
    print_header()
    
    loader = LayoutLoader()
    
    print("🔍 Descobrindo leiautes na Receita Federal...")
    print()
    
    layouts = loader.discover_layouts()
    
    print(f"📋 Encontrados {len(layouts)} leiautes:")
    print()
    
    for layout in layouts:
        cached = loader._cache.get(layout.year)
        status = "📁" if cached else "🆕"
        print(f"  {status} {layout.year}: {layout.title}")
        print(f"      🔗 {layout.url}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Sincroniza leiautes oficiais da DIRPF da Receita Federal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s                    # Sincroniza todos os leiautes
  %(prog)s --year 2025        # Sincroniza apenas o leiaute de 2025
  %(prog)s --force            # Força re-download de todos
  %(prog)s --list             # Lista leiautes baixados
  %(prog)s --discover         # Descobre leiautes disponíveis
        """
    )
    
    parser.add_argument(
        "--year", "-y",
        help="Ano específico para sincronizar (ex: 2025)",
    )
    
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Força re-download mesmo se já existir",
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Lista leiautes baixados",
    )
    
    parser.add_argument(
        "--discover", "-d",
        action="store_true",
        help="Descobre leiautes disponíveis sem baixar",
    )
    
    args = parser.parse_args()
    
    try:
        if args.list:
            cmd_list(args)
        elif args.discover:
            cmd_discover(args)
        else:
            cmd_sync(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

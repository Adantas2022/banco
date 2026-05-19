#!/usr/bin/env python3
"""Reprocessa a confianca de documentos ja extraidos com novo algoritmo centralizado."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pymongo import MongoClient

from irpf_processor.config import get_settings
from irpf_processor.domain.enums import DocumentCategory
from irpf_processor.domain.services import ConfidenceCalculatorFactory, ConfidenceResult


def get_db():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def calculate_new_confidence(extraction_result: dict) -> tuple[float, ConfidenceResult]:
    category_str = extraction_result.get("document_category", "DECLARACAO")
    try:
        category = DocumentCategory(category_str)
    except ValueError:
        category = DocumentCategory.DECLARACAO
    
    extraction_method = extraction_result.get("extraction_method", "digital")
    if extraction_method not in ("digital", "ocr", "mixed"):
        extraction_method = "digital"
    
    ocr_confidence = extraction_result.get("ocr_confidence")
    
    calculator = ConfidenceCalculatorFactory.get_calculator(
        document_category=category,
        extraction_method=extraction_method,
    )
    
    data = extraction_result.get("data", {})
    
    if category == DocumentCategory.RECIBO:
        extracted_data = data
    else:
        extracted_data = data
    
    result = calculator.calculate(
        extracted_data=extracted_data,
        extraction_method=extraction_method,
        ocr_confidence=ocr_confidence,
    )
    
    return result.overall, result


def reprocess_all(dry_run: bool = True, tenant_id: str | None = None, verbose: bool = False):
    db = get_db()
    
    query = {"status": "READY"}
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    documents = list(db["documents"].find(query))
    print(f"Encontrados {len(documents)} documentos para reprocessar")
    
    updated = 0
    unchanged = 0
    errors = 0
    
    confidence_changes = []
    
    for doc in documents:
        doc_id = doc["document_id"]
        tenant = doc["tenant_id"]
        old_confidence = doc.get("confidence", 0.0)
        
        extraction = db["extraction_results"].find_one({
            "document_id": doc_id,
            "tenant_id": tenant,
        })
        
        if not extraction:
            if verbose:
                print(f"  [{doc_id}] Sem resultado de extracao, ignorando")
            errors += 1
            continue
        
        try:
            new_confidence, confidence_result = calculate_new_confidence(extraction)
        except Exception as e:
            if verbose:
                print(f"  [{doc_id}] Erro ao calcular: {e}")
            errors += 1
            continue
        
        diff = new_confidence - old_confidence
        
        if abs(diff) < 0.01:
            unchanged += 1
            continue
        
        confidence_changes.append({
            "doc_id": doc_id,
            "filename": doc.get("filename", "N/A")[:40],
            "old": old_confidence,
            "new": new_confidence,
            "diff": diff,
            "category": extraction.get("document_category", "UNKNOWN"),
            "method": extraction.get("extraction_method", "digital"),
        })
        
        if not dry_run:
            db["documents"].update_one(
                {"document_id": doc_id, "tenant_id": tenant},
                {"$set": {
                    "confidence": new_confidence,
                    "confidence_recalculated_at": datetime.now(timezone.utc),
                }},
            )
            
            db["extraction_results"].update_one(
                {"document_id": doc_id, "tenant_id": tenant},
                {"$set": {
                    "confidence": new_confidence,
                    "confidence_details": confidence_result.to_dict(),
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
        
        updated += 1
    
    print("\n" + "=" * 80)
    print(f"{'DRY RUN - ' if dry_run else ''}RESUMO DO REPROCESSAMENTO")
    print("=" * 80)
    
    if confidence_changes:
        confidence_changes.sort(key=lambda x: x["diff"], reverse=True)
        
        print("\nMaiores mudancas de confianca:")
        print("-" * 80)
        print(f"{'Arquivo':<42} {'Cat':^8} {'Antiga':>8} {'Nova':>8} {'Diff':>8}")
        print("-" * 80)
        
        for change in confidence_changes[:20]:
            print(
                f"{change['filename']:<42} "
                f"{change['category']:^8} "
                f"{change['old']*100:>7.1f}% "
                f"{change['new']*100:>7.1f}% "
                f"{change['diff']*100:>+7.1f}%"
            )
        
        if len(confidence_changes) > 20:
            print(f"... e mais {len(confidence_changes) - 20} documentos")
    
    print("\n" + "-" * 40)
    print(f"Documentos atualizados:   {updated}")
    print(f"Documentos sem mudanca:   {unchanged}")
    print(f"Documentos com erro:      {errors}")
    print(f"Total processado:         {len(documents)}")
    
    if dry_run:
        print("\n[DRY RUN] Nenhuma alteracao foi feita.")
        print("Execute com --execute para aplicar as mudancas.")
    else:
        print("\n[EXECUTADO] Alteracoes aplicadas no banco de dados.")


def main():
    parser = argparse.ArgumentParser(
        description="Reprocessa confianca de documentos com novo algoritmo"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa as alteracoes (default: dry-run)",
    )
    parser.add_argument(
        "--tenant",
        type=str,
        default=None,
        help="Filtrar por tenant_id especifico",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Mostra mais detalhes durante execucao",
    )
    
    args = parser.parse_args()
    
    reprocess_all(
        dry_run=not args.execute,
        tenant_id=args.tenant,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete, func
from backend.models.obra_model import ObraModel

def utc_now():
    return datetime.now(timezone.utc)

MOCK_ID_PREFIXES = ("TEST-", "VAL-", "MOCK-", "DEV-")
KNOWN_MOCK_IDS = {
    "94309291000148-1-000130/2026",
    "88309291000199-1-000045/2026",
    "77104212000188-1-000512/2026",
    "00509018000113-1-001422/2026",
    "82804212000196-1-000214/2026",
}

def is_mock_item(item: Dict[str, Any]) -> bool:
    """Verifica se um item e um registro de teste ou mock."""
    id_pncp = str(item.get("id_pncp") or item.get("numero_controle_pncp") or "").strip()
    fonte = str(item.get("fonte") or "").upper()
    orgao = str(item.get("orgao") or "").upper()
    
    if any(id_pncp.startswith(prefix) for prefix in MOCK_ID_PREFIXES):
        return True
    if id_pncp in KNOWN_MOCK_IDS:
        return True
    if "MOCK" in fonte or "TEST" in fonte or "SANDBOX" in fonte:
        return True
    if "PREFEITURA TESTE" in orgao or "MOCK" in orgao:
        return True
    return False

def delete_mock_obras(db: Session) -> int:
    """Remove definitivamente do banco de dados qualquer registro de teste/mock."""
    stmt = delete(ObraModel).where(
        (ObraModel.id_pncp.like("TEST%")) |
        (ObraModel.id_pncp.like("VAL%")) |
        (ObraModel.id_pncp.like("MOCK%")) |
        (ObraModel.id_pncp.like("DEV%")) |
        (ObraModel.id_pncp.like("%MOCK%")) |
        (ObraModel.fonte.like("%MOCK%")) |
        (ObraModel.fonte.like("%TEST%")) |
        (ObraModel.fonte.like("%SANDBOX%")) |
        (ObraModel.orgao.ilike("%PREFEITURA TESTE%")) |
        (ObraModel.id_pncp.in_(KNOWN_MOCK_IDS))
    )
    result = db.execute(stmt)
    db.commit()
    deleted = result.rowcount
    if deleted > 0:
        print(f"[DATABASE] Removidos {deleted} registros mock/teste do banco de dados.")
    return deleted

def save_obras_batch(db: Session, obras: List[Dict[str, Any]]) -> int:
    """
    Salva ou atualiza uma lista de obras reais no banco de dados (Upsert).
    Ignora completamente quaisquer dados classificados como mock ou teste.
    Evita duplicatas usando o id_pncp como chave primaria.
    Retorna a quantidade de registros processados com sucesso.
    """
    if not obras:
        return 0

    inserted_count = 0
    updated_count = 0

    for item in obras:
        # NUNCA salvar dados de mock/teste no banco de dados
        if is_mock_item(item):
            continue

        id_pncp = str(item.get("id_pncp") or item.get("numero_controle_pncp") or "").strip()
        if not id_pncp:
            continue

        existing = db.get(ObraModel, id_pncp)
        if existing:
            # Atualiza campos se necessario
            existing.orgao = item.get("orgao") or existing.orgao
            existing.municipio = item.get("municipio") or existing.municipio
            existing.uf = item.get("uf") or existing.uf
            existing.objeto = item.get("objeto") or existing.objeto
            existing.valor_estimado = item.get("valor_estimado") if item.get("valor_estimado") is not None else existing.valor_estimado
            existing.data_publicacao = str(item.get("data_publicacao") or existing.data_publicacao)
            existing.modalidade = item.get("modalidade") or existing.modalidade
            existing.link_pncp = item.get("link_pncp") or existing.link_pncp
            existing.fonte = "PNCP_REAL"
            # Atualiza timestamp para renovar a retencao caso tenha sido re-capturada
            existing.created_at = utc_now()
            updated_count += 1
        else:
            nova_obra = ObraModel(
                id_pncp=id_pncp,
                numero_controle_pncp=item.get("numero_controle_pncp"),
                orgao=item.get("orgao") or "Nao informado",
                municipio=item.get("municipio"),
                uf=(item.get("uf") or "BR").upper().strip(),
                objeto=item.get("objeto") or "",
                valor_estimado=item.get("valor_estimado"),
                data_publicacao=str(item.get("data_publicacao") or ""),
                modalidade=item.get("modalidade"),
                link_pncp=item.get("link_pncp"),
                fonte="PNCP_REAL",
                created_at=utc_now()
            )
            db.add(nova_obra)
            inserted_count += 1

    db.commit()
    return inserted_count + updated_count

def cleanup_expired_obras(db: Session, max_age_days: int = 2) -> int:
    """
    Exclui automaticamente do banco de dados todas as obras capturadas ha mais de X dias (padrao: 2 dias = 48 horas).
    Retorna a quantidade de obras excluidas.
    """
    cutoff_date = utc_now() - timedelta(days=max_age_days)
    
    stmt = delete(ObraModel).where(ObraModel.created_at < cutoff_date)
    result = db.execute(stmt)
    db.commit()
    
    deleted_count = result.rowcount
    if deleted_count > 0:
        print(f"[DATABASE CLEANUP] Excluidas {deleted_count} obras expiradas (mais antigas que {max_age_days} dias / {cutoff_date.strftime('%d/%m/%Y %H:%M')}).")
    return deleted_count

def get_obras_from_db(
    db: Session,
    uf: Optional[str] = None,
    modalidade: Optional[Any] = None,
    data_inicial: Optional[str] = None,
    data_final: Optional[str] = None,
    limit: int = 300
) -> List[Dict[str, Any]]:
    """Consulta apenas obras reais salvas no banco de dados local com filtros opcionais."""
    stmt = select(ObraModel).where(
        ~ObraModel.id_pncp.like("TEST%"),
        ~ObraModel.id_pncp.like("VAL%"),
        ~ObraModel.id_pncp.like("MOCK%"),
        ~ObraModel.id_pncp.like("DEV%"),
        ~ObraModel.id_pncp.like("%MOCK%"),
        ~ObraModel.fonte.like("%MOCK%"),
        ~ObraModel.fonte.like("%TEST%"),
        ~ObraModel.id_pncp.in_(KNOWN_MOCK_IDS)
    )
    
    if uf and uf != "TODOS":
        stmt = stmt.where(ObraModel.uf == uf.upper().strip())
        
    if modalidade is not None and str(modalidade) != "0" and modalidade != "":
        if str(modalidade) == "4":
            stmt = stmt.where(ObraModel.modalidade.ilike("%concorr%"))
        elif str(modalidade) == "6":
            stmt = stmt.where(ObraModel.modalidade.ilike("%preg%"))
        elif isinstance(modalidade, str):
            stmt = stmt.where(ObraModel.modalidade.ilike(f"%{modalidade}%"))
            
    if data_inicial:
        data_ini_iso = f"{data_inicial[:4]}-{data_inicial[4:6]}-{data_inicial[6:8]}"
        stmt = stmt.where(ObraModel.data_publicacao >= data_ini_iso)
        
    if data_final:
        data_fim_iso = f"{data_final[:4]}-{data_final[4:6]}-{data_final[6:8]}T23:59:59"
        stmt = stmt.where(ObraModel.data_publicacao <= data_fim_iso)
        
    stmt = stmt.order_by(ObraModel.data_publicacao.desc(), ObraModel.created_at.desc()).limit(limit)
    records = db.scalars(stmt).all()
    return [r.to_dict() for r in records]

def get_db_stats(db: Session) -> Dict[str, Any]:
    """Retorna estatisticas de armazenamento e retencao do banco de dados (excluindo mocks)."""
    # Executa limpeza preventiva antes de retornar estatisticas
    delete_mock_obras(db)
    
    total = db.scalar(
        select(func.count()).select_from(ObraModel).where(
            ~ObraModel.id_pncp.like("TEST%"),
            ~ObraModel.id_pncp.like("VAL%"),
            ~ObraModel.id_pncp.like("%MOCK%"),
            ~ObraModel.id_pncp.in_(KNOWN_MOCK_IDS)
        )
    ) or 0
    
    oldest = db.scalar(select(func.min(ObraModel.created_at)))
    newest = db.scalar(select(func.max(ObraModel.created_at)))
    
    return {
        "total_obras_armazenadas": total,
        "registro_mais_antigo": oldest.isoformat() if oldest else None,
        "registro_mais_recente": newest.isoformat() if newest else None,
        "politica_retencao": "Exclusao automatica apos 2 dias (48 horas)"
    }

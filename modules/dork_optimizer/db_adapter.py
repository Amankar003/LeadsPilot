import json
from datetime import datetime
from config.database import get_db_session
from modules.database.models import (
    DorkSourceData,
    DorkTrendAnalysis,
    DorkRecommendation,
    DorkHistory,
    DorkPipelineState
)
from modules.dork_optimizer.services.dedupe import generate_source_hash, generate_fingerprint
from sqlalchemy import func

def save_source_data(items: list[dict]) -> dict:
    inserted = 0
    skipped = 0
    with get_db_session() as db:
        for item in items:
            source_hash = generate_source_hash(item)
            
            # Check if exists
            exists = db.query(DorkSourceData).filter(DorkSourceData.source_hash == source_hash).first()
            if exists:
                skipped += 1
                continue
                
            new_record = DorkSourceData(
                source_name=item.get("source_name", ""),
                source_type=item.get("source_type", ""),
                title=item.get("title", ""),
                url=item.get("url", ""),
                raw_text=item.get("raw_text", ""),
                country=item.get("country", ""),
                region=item.get("region", ""),
                keyword=item.get("keyword", ""),
                published_at=item.get("published_at", ""),
                source_hash=source_hash
            )
            db.add(new_record)
            inserted += 1
        db.commit()
    return {"inserted": inserted, "skipped": skipped}

def get_today_source_data() -> list[dict]:
    today = datetime.utcnow().date()
    with get_db_session() as db:
        records = db.query(DorkSourceData).filter(
            func.date(DorkSourceData.fetched_at) == today,
            DorkSourceData.status == 'fresh'
        ).order_by(DorkSourceData.id.desc()).all()
        return [
            {
                "id": r.id,
                "source_name": r.source_name,
                "source_type": r.source_type,
                "title": r.title,
                "url": r.url,
                "raw_text": r.raw_text,
                "country": r.country,
                "region": r.region,
                "keyword": r.keyword,
                "published_at": r.published_at,
                "fetched_at": r.fetched_at.strftime("%Y-%m-%d %H:%M:%S") if r.fetched_at else "",
                "source_hash": r.source_hash,
                "status": r.status
            }
            for r in records
        ]

def get_source_summary() -> dict:
    today = datetime.utcnow().date()
    with get_db_session() as db:
        total = db.query(func.count(DorkSourceData.id)).filter(func.date(DorkSourceData.fetched_at) == today).scalar()
        
        counts_by_source = db.query(DorkSourceData.source_name, func.count(DorkSourceData.id)).filter(
            func.date(DorkSourceData.fetched_at) == today
        ).group_by(DorkSourceData.source_name).all()
        
        by_source = {name: count for name, count in counts_by_source}
        
        has_seed = db.query(func.count(DorkSourceData.id)).filter(
            func.date(DorkSourceData.fetched_at) == today,
            DorkSourceData.source_type == 'seed'
        ).scalar() > 0
        
        return {"total_today": total, "by_source": by_source, "seed_used": has_seed}

def save_trend_analysis(trends: list[dict]) -> list[dict]:
    saved = []
    with get_db_session() as db:
        for trend in trends:
            new_trend = DorkTrendAnalysis(
                trend_name=trend.get("trend_name", ""),
                country=trend.get("country", ""),
                region=trend.get("region", ""),
                sector=trend.get("sector", ""),
                domain=trend.get("domain", ""),
                business_requirements=json.dumps(trend.get("business_requirements", [])),
                why_this_region=trend.get("why_this_region", ""),
                why_this_sector=trend.get("why_this_sector", ""),
                recommended_service=trend.get("recommended_service", ""),
                confidence_score=trend.get("confidence_score", 0),
                source_ids=json.dumps(trend.get("source_ids", []))
            )
            db.add(new_trend)
            db.flush()
            trend["id"] = new_trend.id
            saved.append(trend)
        db.commit()
    return saved

def get_today_trends() -> list[dict]:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_session() as db:
        records = db.query(DorkTrendAnalysis).filter(
            DorkTrendAnalysis.analysis_date == today_str
        ).order_by(DorkTrendAnalysis.confidence_score.desc()).all()
        
        result = []
        for r in records:
            d = {
                "id": r.id,
                "analysis_date": r.analysis_date,
                "trend_name": r.trend_name,
                "country": r.country,
                "region": r.region,
                "sector": r.sector,
                "domain": r.domain,
                "why_this_region": r.why_this_region,
                "why_this_sector": r.why_this_sector,
                "recommended_service": r.recommended_service,
                "confidence_score": r.confidence_score,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
            }
            try:
                d["business_requirements"] = json.loads(r.business_requirements or "[]")
            except Exception:
                d["business_requirements"] = []
                
            try:
                d["source_ids"] = json.loads(r.source_ids or "[]")
            except Exception:
                d["source_ids"] = []
            
            result.append(d)
        return result

def save_recommendation(rec: dict) -> int:
    fingerprint = generate_fingerprint(
        rec.get("trend_name", ""),
        rec.get("country", ""),
        rec.get("region", ""),
        rec.get("sector", ""),
        rec.get("recommended_service", "")
    )
    
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_session() as db:
        existing = db.query(DorkRecommendation).filter(
            DorkRecommendation.fingerprint == fingerprint,
            DorkRecommendation.recommendation_date == today_str
        ).first()
        
        if existing:
            if rec.get("opportunity_score", 0) > (existing.opportunity_score or 0):
                existing.keywords = json.dumps(rec.get("keywords", []))
                existing.dorks = json.dumps(rec.get("dorks", []))
                existing.urls = json.dumps(rec.get("urls", []))
                existing.why_this_dork = json.dumps(rec.get("why_this_dork", []))
                existing.opportunity_score = rec.get("opportunity_score", 0)
                existing.status = rec.get("status", "ready")
                db.commit()
            return existing.id
        else:
            new_rec = DorkRecommendation(
                trend_id=rec.get("trend_id"),
                trend_name=rec.get("trend_name", ""),
                country=rec.get("country", ""),
                region=rec.get("region", ""),
                sector=rec.get("sector", ""),
                domain=rec.get("domain", ""),
                recommended_service=rec.get("recommended_service", ""),
                keywords=json.dumps(rec.get("keywords", [])),
                dorks=json.dumps(rec.get("dorks", [])),
                urls=json.dumps(rec.get("urls", [])),
                why_this_dork=json.dumps(rec.get("why_this_dork", [])),
                opportunity_score=rec.get("opportunity_score", 0),
                status=rec.get("status", "ready"),
                fingerprint=fingerprint
            )
            db.add(new_rec)
            db.commit()
            db.refresh(new_rec)
            return new_rec.id

def _parse_recommendation(r) -> dict:
    d = {
        "id": r.id,
        "recommendation_date": r.recommendation_date,
        "trend_id": r.trend_id,
        "trend_name": r.trend_name,
        "country": r.country,
        "region": r.region,
        "sector": r.sector,
        "domain": r.domain,
        "recommended_service": r.recommended_service,
        "opportunity_score": r.opportunity_score,
        "status": r.status,
        "fingerprint": r.fingerprint,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
    }
    for field in ["keywords", "dorks", "urls", "why_this_dork"]:
        try:
            d[field] = json.loads(getattr(r, field) or "[]")
        except Exception:
            d[field] = []
    return d

def get_today_recommendations() -> list[dict]:
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    with get_db_session() as db:
        records = db.query(DorkRecommendation).filter(
            DorkRecommendation.recommendation_date == today_str,
            DorkRecommendation.status == 'ready'
        ).order_by(DorkRecommendation.opportunity_score.desc()).all()
        
        if not records:
            records = db.query(DorkRecommendation).filter(
                DorkRecommendation.status == 'ready'
            ).order_by(DorkRecommendation.id.desc()).limit(20).all()
            
        return [_parse_recommendation(r) for r in records]

def get_recommendation_history(limit: int = 100) -> list[dict]:
    with get_db_session() as db:
        records = db.query(DorkRecommendation).order_by(DorkRecommendation.created_at.desc()).limit(limit).all()
        return [_parse_recommendation(r) for r in records]

def mark_dork_used(dork_text: str, dork_hash: str, country: str = "", region: str = "", sector: str = ""):
    with get_db_session() as db:
        exists = db.query(DorkHistory).filter(DorkHistory.dork_hash == dork_hash).first()
        if not exists:
            # We don't have user_id, use a default user
            from modules.database.models import User
            user = db.query(User).first()
            if not user:
                user = User(full_name="System", email="system@leadpilot.ai", hashed_password="")
                db.add(user)
                db.flush()
                
            new_hist = DorkHistory(
                user_id=user.id,
                dork_text=dork_text,
                dork_hash=dork_hash,
                country=country,
                region=region,
                sector=sector,
                status='used'
            )
            db.add(new_hist)
            db.commit()

def is_dork_used(dork_hash: str) -> bool:
    with get_db_session() as db:
        return db.query(DorkHistory).filter(DorkHistory.dork_hash == dork_hash).first() is not None

def get_used_dork_hashes() -> set:
    with get_db_session() as db:
        records = db.query(DorkHistory.dork_hash).all()
        return {r[0] for r in records if r[0]}

def save_pipeline_status(status: str, message: str = ""):
    with get_db_session() as db:
        stat_rec = db.query(DorkPipelineState).filter(DorkPipelineState.key == 'status').first()
        if stat_rec:
            stat_rec.value = status
        else:
            db.add(DorkPipelineState(key='status', value=status))
            
        msg_rec = db.query(DorkPipelineState).filter(DorkPipelineState.key == 'message').first()
        if msg_rec:
            msg_rec.value = message
        else:
            db.add(DorkPipelineState(key='message', value=message))
        db.commit()

def get_pipeline_status() -> dict:
    with get_db_session() as db:
        stat_rec = db.query(DorkPipelineState).filter(DorkPipelineState.key == 'status').first()
        msg_rec = db.query(DorkPipelineState).filter(DorkPipelineState.key == 'message').first()
        
        return {
            "status": stat_rec.value if stat_rec else "idle",
            "message": msg_rec.value if msg_rec else ""
        }

def delete_india_recommendations() -> int:
    from modules.dork_optimizer.services.market_filter import is_india_market
    from modules.dork_optimizer.dork_generator import is_weak_dork
    
    deleted_count = 0
    updated_count = 0
    with get_db_session() as db:
        records = db.query(DorkRecommendation).all()
        for r in records:
            item_dict = {
                "country": r.country,
                "region": r.region,
                "trend_name": r.trend_name
            }
            
            try:
                dorks_list = json.loads(r.dorks or "[]")
            except Exception:
                dorks_list = [r.dorks] if r.dorks else []
                
            item_dict["dorks"] = dorks_list
            
            if is_india_market(item_dict):
                db.delete(r)
                deleted_count += 1
                continue
                
            valid_dorks = [d for d in dorks_list if not is_weak_dork(d)]
            if not valid_dorks:
                db.delete(r)
                deleted_count += 1
            else:
                try:
                    why_list = json.loads(r.why_this_dork or "[]")
                except Exception:
                    why_list = []
                    
                valid_why = [w for w in why_list if isinstance(w, dict) and "dork" in w and not is_weak_dork(w["dork"])]
                
                if len(valid_dorks) < len(dorks_list):
                    r.dorks = json.dumps(valid_dorks)
                    r.why_this_dork = json.dumps(valid_why)
                    updated_count += 1
                    
        db.commit()
    print(f"[Cleanup] Updated dorks list for {updated_count} rows.")
    return deleted_count + updated_count

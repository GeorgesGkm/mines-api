from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, not_, String, cast
from datetime import date
from src.core.database import get_db
from src.mission import models, schemas
from src.auth.dependencies import allow_admin, allow_agent, allow_chef

router = APIRouter(
    prefix="/statistiques",
    tags=["Indicateurs et Tableau de Bord"]
)

@router.get("/dashboard", response_model=dict)
def obtenir_statistiques_tableau_de_bord(
    db: Session = Depends(get_db),
    current_user = Depends(allow_chef)
):
    """
    Retourne l'ensemble des indicateurs clés consolidés pour le tableau de bord de l'administration.
    """
    
    # 1) Nombre total des entreprises
    total_entreprises = db.query(func.count(models.Entreprise.code)).scalar() or 0

    # 2) Entreprises actives (ayant au moins un titre minier valide / non déchu)
    entreprises_actives = db.query(func.count(func.distinct(models.Demande.entreprise_code)))\
        .join(models.TitreMinier, models.Demande.numdem == models.TitreMinier.demande_num)\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Renouvelé")).scalar() or 0
    
    # 3) Entreprises déchues (Entreprises dont tous les titres sont déchus ou sans aucun titre valide)
    entreprises_dechues = db.query(func.count(func.distinct(models.Demande.entreprise_code)))\
        .join(models.TitreMinier, models.Demande.numdem == models.TitreMinier.demande_num)\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Déchu")).scalar() or 0
    

    entreprises_refuse = db.query(func.count(func.distinct(models.Demande.entreprise_code)))\
        .join(models.TitreMinier, models.Demande.numdem == models.TitreMinier.demande_num)\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Refusé")).scalar() or 0

    # 3) Recettes systèmes (Somme fictive ou consolidée basée sur vos tables financières/redevances)
    # Remplacer par votre modèle de transaction/recette réel si existant
    total_recettes = db.query(func.sum(models.ProcesVerbal.montant_amande)).scalar() or 0.0

    # 4) Missions en cours
    missions_total = db.query(func.count(models.Mission.n_ordre)).scalar() or 0

    # 5) Rapports clotures
    missions_en_cours = db.query(func.count(models.Mission.n_ordre))\
        .filter(models.Mission.statut == "EN_COURS").scalar() or 0

    missions_cloture = db.query(func.count(models.Mission.n_ordre))\
        .filter(models.Mission.statut == "CLOTURE").scalar() or 0

    # 7) Nombre d'agents
    nombre_agents = db.query(func.count(models.Agent.matricule)).scalar() or 0

    # 8) Nombre total des titres
    total_titres = db.query(func.count(models.TitreMinier.naretag)).scalar() or 0

    # 9) Titres déchus (Statut égal à "Déchu")
    titres_dechus = db.query(func.count(models.TitreMinier.naretag))\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Déchu")).scalar() or 0

    # 10) Titres renouvelés / valides (Statut égal à "Valide" ou "Renouvelé")
    titres_renouveles = db.query(func.count(models.TitreMinier.naretag))\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Renouvelé")).scalar() or 0
    
    titres_refuse = db.query(func.count(models.TitreMinier.naretag))\
        .join(models.EtatTitre, models.TitreMinier.codetattit == models.EtatTitre.codetattit)\
        .filter(models.EtatTitre.libetattit.ilike("Refusé")).scalar() or 0
    

    demandes_rejetees = db.query(func.count(models.Demande.numdem))\
        .filter(models.Demande.statut == models.StatutInstruction.REJETE).scalar() or 0

    # 2. Demandes Validées (Transmises au CAMI)
    demandes_validees = db.query(func.count(models.Demande.numdem))\
        .filter(models.Demande.statut == models.StatutInstruction.VALIDE).scalar() or 0

    # 3. Demandes en cours d'Analyse (Regroupe ANALYSE_PROVINCIALE, ANALYSE_MINISTRE_PROV et ANALYSE_DIRECTION_MINES)
    demandes_en_analyse = db.query(func.count(models.Demande.numdem))\
        .filter(cast(models.Demande.statut, String).like("%ANALYSE%")).scalar() or 0

    # 4. Nombre total de demandes (Toutes catégories confondues)
    total_demandes = db.query(func.count(models.Demande.numdem)).scalar() or 0

    
    return {
        "entreprises_actives": entreprises_actives,
        "entreprises_dechues": entreprises_dechues,
        "entreprises_refuse": entreprises_refuse,
        "total_entreprises": total_entreprises,
        "recettes_systeme": total_recettes,
        "missions_en_cours": missions_en_cours,
        "mission_cloture": missions_cloture,
        "mission_total": missions_total,
        "nombre_agents": nombre_agents,
        "total_titres": total_titres,
        "titres_dechus": titres_dechus,
        "titres_renouveles": titres_renouveles,
        "titres_refuse": titres_refuse,
        "demandes_rejete": demandes_rejetees,
        "demandes_valide": demandes_validees,
        "demande_analyse": demandes_en_analyse,
        "total_demandes": total_demandes

    }

@router.get("/agent", response_model=dict)
def obtenir_statistiques_agent_connecte(
    db: Session = Depends(get_db),
    current_user = Depends(allow_agent)
):
    """
    Indicateurs personnalisés pour l'agent connecté .
    """
    # 1. Vérification de la liaison avec la table Agent
    if not current_user.agent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet utilisateur n'est associé à aucun compte agent dans le personnel."
        )
        
    # Extraction de l'ID de l'agent 
    agent_id = current_user.agent.matricule

    # 2. Requête de base pour les missions de l'agent via la table pivot
    query_missions_agent = db.query(models.Mission)\
        .join(models.mission_agent)\
        .filter(models.mission_agent.c.agent_id == agent_id)

    # 3. Extraction des compteurs de missions
    missions_total = query_missions_agent.count()
    missions_en_cours = query_missions_agent.filter(models.Mission.statut == "EN_COURS").count()
    missions_cloture = query_missions_agent.filter(models.Mission.statut == "CLOTURE").count()

    # 4. Calcul des recettes (amandes) générées par cet agent via ses missions
    recettes_agent = db.query(func.sum(models.ProcesVerbal.montant_amande))\
        .join(models.Mission, models.ProcesVerbal.mission_id == models.Mission.n_ordre)\
        .join(models.mission_agent)\
        .filter(models.mission_agent.c.agent_id == agent_id).scalar() or 0.0

    # 5. Nombre de Procès-Verbaux dressés par l'agent
    total_pv_emis = db.query(func.count(models.ProcesVerbal.num_pv))\
        .join(models.Mission, models.ProcesVerbal.mission_id == models.Mission.n_ordre)\
        .join(models.mission_agent)\
        .filter(models.mission_agent.c.agent_id == agent_id).scalar() or 0

    return {
        "agent_id": agent_id,
        "missions_total": missions_total,
        "missions_en_cours": missions_en_cours,
        "missions_cloture": missions_cloture,
        "recettes_generees": recettes_agent,
        "total_pv_emis": total_pv_emis
    }
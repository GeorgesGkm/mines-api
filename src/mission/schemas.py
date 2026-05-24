from pydantic import BaseModel, ConfigDict
from datetime import date
from typing import List, Optional

# --- CONFIGURATION COMMUNE ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- SUBSTANCE & PRODUCTION JOINTURE ---
class ProductionSubstanceBase(BaseSchema):
    centre_ach: Optional[str] = None
    nb_achet: Optional[int] = None
    nb_exploit: Optional[int] = None
    valbon: Optional[float] = None
    val_decl: Optional[float] = None
    mpc_decl: Optional[str] = None

class ProductionSubstanceResponse(ProductionSubstanceBase):
    substance_contrat: str


# --- AGENT ---
class AgentBase(BaseSchema):
    matricule: str
    nom: str
    postnom: Optional[str] = None
    prenom: Optional[str] = None
    fonction: Optional[str] = None
    grade: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class AgentResponse(AgentBase):
    pass

class AgentUpdate(BaseSchema):
    matricule: Optional[str] = None
    nom: Optional[str] = None
    postnom: Optional[str] = None
    prenom: Optional[str] = None
    fonction: Optional[str] = None
    grade: Optional[str] = None

class AgentPaginationResponse(BaseModel):
    total_items: int     
    total_pages: int     
    current_page: int    
    page_size: int       
    items: List[AgentResponse] 

    model_config = ConfigDict(from_attributes=True)


# --- QUESTION REPONSE ---
class QuestionReponseBase(BaseSchema):
    num_ordre: int
    question: str
    response: str

class QuestionReponseCreate(QuestionReponseBase):
    num_pv: str

class QuestionReponseResponse(QuestionReponseBase):
    id: int


# --- PROCES VERBAL ---
class ProcesVerbalBase(BaseSchema):
    num_pv: str
    date_pv: date
    infraction: Optional[str] = None
    montant_amande: Optional[float] = None
    type_code: Optional[int] = None
    mission_id: int

# Schéma pour la mise à jour partielle du PV
class ProcesVerbalUpdate(BaseModel):
    date_pv: Optional[date] = None
    infraction: Optional[str] = None
    montant_amande: Optional[float] = None
    type_code: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ProcesVerbalResponse(ProcesVerbalBase):
    questions_reponses: List[QuestionReponseResponse] = []

# Schéma pour la réponse paginée
class PVPaginationResponse(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    items: List[ProcesVerbalResponse]

    model_config = ConfigDict(from_attributes=True)

class QuestionReponseBase(BaseModel):
    num_ordre: int
    question: str
    response: str

class QuestionReponseUpdate(BaseModel):
    num_ordre: Optional[int] = None
    question: Optional[str] = None
    response: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ProcesVerbalCreate(BaseModel):
    num_pv: str
    date_pv: date
    infraction: str
    montant_amande: Optional[float] = 0.0
    mission_id: int
    type_code: int
    
    questions: Optional[List[QuestionReponseBase]] = []

    model_config = ConfigDict(from_attributes=True)

# --- TYPE PV ---
class TypePVBase(BaseSchema):
    type_nom: str

class TypePVResponse(TypePVBase):
    code_type: int

    model_config = ConfigDict(from_attributes=True)    

class TypePVCreate(TypePVBase):
    pass

class TypePVUpdate(BaseModel):
   type_nom: Optional[str] = None

   model_config = ConfigDict(from_attributes=True)


# --- MISSION ---
class MissionBase(BaseSchema):
    objet: str
    province: str
    date_debut: date
    date_fin: date
    statut: str
    mode_transport: str
    entreprise_code: str

class MissionCreate(MissionBase):
    agent_matricules: List[str] = [] # Liste des ID d'agents affectés à la création

class MissionResponse(MissionBase):
    n_ordre: int
    note_explicative: str
    agents: List[AgentResponse] = []
    proces_verbal: Optional[ProcesVerbalBase] = None

# Schéma pour la mise à jour partielle (PATCH)
class MissionUpdate(BaseSchema):
    objet: Optional[str] = None
    province: Optional[str] = None
    date_debut: Optional[date] = None
    date_fin: Optional[date] = None
    mode_transport: Optional[str] = None
    entreprise_code: Optional[str] = None

# Schéma pour la réponse paginée
class MissionPaginationResponse(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    items: List[MissionResponse]

    model_config = ConfigDict(from_attributes=True)

class MissionStatutUpdate(BaseModel):
    statut: str # 'VALIDE_DIR', 'APPROUVE_SG', 'SIGNE_MINISTRE', 'RETIRE', 'EN_COURS','CLOTURE', 'ANNULE'

    model_config = ConfigDict(from_attributes=True)

class MissionClotureRequest(BaseModel):
    commentaire: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class MissionPaginationResponse(BaseModel):
    total_items: int         # Nombre total de missions correspondant au filtre
    total_pages: int         # Nombre total de pages disponibles
    current_page: int        # Page actuelle
    page_size: int           # Taille de la page
    items: List[MissionResponse] # La liste des missions pour la page actuelle

    model_config = ConfigDict(from_attributes=True)

# --- ENTREPRISE ---
class EntrepriseBase(BaseSchema):
    code: str
    nomenclature: Optional[str] = None
    rccm: Optional[str] = None
    idnat: Optional[str] = None
    adresse: Optional[str] = None
    n_impot: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    n_comptebancaire: Optional[str] = None

class EntreprisePaginationResponse(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    page_size: int
    items: List[EntrepriseResponse]

    model_config = ConfigDict(from_attributes=True)

class EntrepriseUpdate(BaseModel):
    nomenclature: Optional[str] = None
    rccm: Optional[str] = None
    idnat: Optional[str] = None
    adresse: Optional[str] = None
    n_impot: Optional[str] = None
    province: Optional[str] = None
    phone: Optional[str] = None
    n_comptebancaire: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class EntrepriseCreate(EntrepriseBase):
    pass


class EntrepriseResponse(EntrepriseBase):
    pass


# --- DÉTAILS DE LA SUBSTANCE DANS LE PAYLOAD ---
class SubstanceProductionCreate(BaseModel):
    libSub: str
    mont: Optional[float] = 0.0
    carat: Optional[float] = 0.0
    date_cont: Optional[date] = None
    
    centre_ach: Optional[str] = None
    nb_exp: Optional[int] = 0
    valbon: Optional[float] = 0.0
    val_decl: Optional[float] = 0.0
    mpc_decl: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class ProductionCreate(BaseModel):
    code_prod: str        
    datprod: date
    nbCarat: Optional[float] = 0.0
    entreprise_code: str  
    mission_id: int       
    
    substances_declarees: List[SubstanceProductionCreate]

    model_config = ConfigDict(from_attributes=True)

class ProductionSubstanceResponse(BaseModel):
    substance_code: int
    centre_ach: Optional[str]
    nb_exp: Optional[int]
    valbon: Optional[float]
    val_decl: Optional[float]
    mpc_decl: Optional[int]

    model_config = ConfigDict(from_attributes=True)

class ProductionResponse(BaseModel):
    code_prod: str
    datprod: date
    nbCarat: Optional[float]
    entreprise_code: str
    mission_id: int
    substances: List[ProductionSubstanceResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ProductionUpdate(BaseModel):
    datprod: Optional[date] = None
    nbCarat: Optional[float] = None
    entreprise_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SubstanceUpdate(BaseModel):
    libSub: Optional[str] = None
    mont: Optional[float] = None
    carat: Optional[float] = None
    date_cont: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)

class SubstanceBase(BaseModel):
    libSub: str
    mont: Optional[float] = 0.0
    carat: Optional[float] = 0.0
    date_cont: Optional[date] = None

class SubstanceCreate(SubstanceBase):
    pass

class SubstanceResponse(SubstanceBase):
    code_sub: int

    model_config = ConfigDict(from_attributes=True)

class ProductionSubstanceUpdate(BaseModel):
    centre_ach: Optional[str] = None
    nb_exp: Optional[int] = None
    valbon: Optional[float] = None
    val_decl: Optional[float] = None
    mpc_decl: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# --- TITRE MINIER ---
class TitreMinierBase(BaseSchema):
    numArret: str
    doc_etude: Optional[str] = None
    doc_impactEnvir: Optional[str] = None
    date_octroi: Optional[date] = None
    date_fin: Optional[date] = None
    etat: Optional[str] = None
    entreprise_code: str
    type_id: int

class TitreMinierCreate(TitreMinierBase):
    pass

class TitreMinierResponse(TitreMinierBase):
    pass
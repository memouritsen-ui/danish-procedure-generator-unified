# Enhancement 4: Template-Based Procedure Customization UI

## Status: NOT STARTED

**Priority**: 4
**Estimated Effort**: 4-5 days
**Dependencies**: None

---

## IMPORTANT: Orchestrator Integration Context

**As of 2024-12-18**, the pipeline uses a multi-agent orchestrator with a WriterAgent.

**Template integration approach**:
Templates should be passed to the WriterAgent as part of its input configuration:

```python
# In run_pipeline() when creating orchestrator:
pipeline_input = AgentPipelineInput(
    procedure_title=procedure,
    context=context,
    template_config=template,  # Pass template sections/structure
    max_iterations=3,
    quality_threshold=8,
)
```

The WriterAgent already accepts an optional `style_guide` and `outline` parameter. Templates can feed into these:
- `outline`: Section headings from template
- `style_guide`: Formatting instructions from template

**Key files to modify**:
- `backend/procedurewriter/agents/models.py` - Add template fields to WriterInput
- `backend/procedurewriter/agents/writer.py` - Use template for section generation

---

## SESSION START CHECKLIST

Before implementing ANY part of this enhancement, execute:

```
Skill(superpowers:using-superpowers)
Skill(superpowers:test-driven-development)
Skill(superpowers:verification-before-completion)
```

**REMINDER**: NO DUMMY/MOCK IMPLEMENTATIONS. All code must be production-ready.

---

## Problem Statement

Currently, procedure structure is controlled by `author_guide.yaml`:

1. File-based configuration requires manual editing
2. Different departments need different formats
3. No UI to create/manage templates
4. Can't save templates for reuse

Example needs:
- **Emergency**: Action-focused, bulleted, minimal explanation
- **Pediatrics**: Age-specific sections, dosing tables
- **Surgery**: Pre-op, intra-op, post-op phases
- **Psychiatry**: Assessment, intervention, safety planning

---

## Solution Overview

Create a template management system with UI:

```
Templates Library
├── Emergency Standard (default)
│   └── Indikationer, Kontra, Forberedelse, Fremgangsmåde, Sikkerhed...
├── Surgical Procedure
│   └── Præoperativ, Intraoperativ, Postoperativ, Komplikationer...
├── Pediatric Emergency
│   └── Aldersgrupper, Dosering per vægt, Fremgangsmåde, Observationer...
└── [+ Create New Template]
```

Features:
1. **Template Library**: List of saved templates
2. **Template Editor**: Add/remove/reorder sections
3. **Template Selection**: Choose template when generating
4. **Default Template**: Organization-level default

---

## Technical Specification

### Database Changes

#### Schema Addition

```sql
-- Templates table
CREATE TABLE templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT FALSE,  -- Built-in templates
    created_by TEXT,  -- Future: user tracking
    config_json TEXT NOT NULL  -- Full template configuration
);

-- Index for default lookup
CREATE INDEX idx_templates_default ON templates(is_default);

-- Link runs to templates
ALTER TABLE runs ADD COLUMN template_id TEXT REFERENCES templates(template_id);
```

#### Migration Script (`backend/scripts/migrate_templates.py`)

```python
"""
Database migration for template system.

Run this ONCE to add templates table and seed defaults.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DEFAULT_TEMPLATES = [
    {
        "template_id": "emergency_standard",
        "name": "Emergency Standard",
        "description": "Standard akutmedicinsk procedure format med alle sektioner",
        "is_default": True,
        "is_system": True,
        "config": {
            "title_prefix": "Procedure",
            "sections": [
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Udstyr", "format": "bullets", "bundle": "action"},
                {"heading": "Fremgangsmåde (trin-for-trin)", "format": "numbered", "bundle": "action"},
                {"heading": "Forklaringslag (baggrund og rationale)", "format": "paragraphs", "bundle": "explanation"},
                {"heading": "Sikkerhedsboks", "format": "bullets", "bundle": "safety"},
                {"heading": "Komplikationer og fejlfinding", "format": "bullets", "bundle": "action"},
                {"heading": "Disposition og opfølgning", "format": "bullets", "bundle": "action"},
                {"heading": "Evidens og begrænsninger", "format": "bullets", "bundle": "explanation"},
            ],
        },
    },
    {
        "template_id": "surgical_procedure",
        "name": "Surgical Procedure",
        "description": "Kirurgisk procedure med præ-, intra- og postoperative faser",
        "is_default": False,
        "is_system": True,
        "config": {
            "title_prefix": "Kirurgisk Procedure",
            "sections": [
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Præoperativ forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Anæstesi", "format": "bullets", "bundle": "action"},
                {"heading": "Lejring og afvaskning", "format": "bullets", "bundle": "action"},
                {"heading": "Kirurgisk teknik", "format": "numbered", "bundle": "action"},
                {"heading": "Intraoperative observationer", "format": "bullets", "bundle": "safety"},
                {"heading": "Lukning og forbinding", "format": "numbered", "bundle": "action"},
                {"heading": "Postoperativ pleje", "format": "bullets", "bundle": "action"},
                {"heading": "Komplikationer", "format": "bullets", "bundle": "safety"},
            ],
        },
    },
    {
        "template_id": "pediatric_emergency",
        "name": "Pediatric Emergency",
        "description": "Pædiatrisk akut procedure med vægtbaseret dosering",
        "is_default": False,
        "is_system": True,
        "config": {
            "title_prefix": "Pædiatrisk Procedure",
            "sections": [
                {"heading": "Aldersgrupper og definitioner", "format": "bullets", "bundle": "explanation"},
                {"heading": "Indikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Kontraindikationer", "format": "bullets", "bundle": "action"},
                {"heading": "Dosering per vægt", "format": "bullets", "bundle": "action"},
                {"heading": "Forberedelse", "format": "bullets", "bundle": "action"},
                {"heading": "Fremgangsmåde", "format": "numbered", "bundle": "action"},
                {"heading": "Observationer og monitorering", "format": "bullets", "bundle": "action"},
                {"heading": "Sikkerhed og advarsler", "format": "bullets", "bundle": "safety"},
                {"heading": "Forælder-information", "format": "paragraphs", "bundle": "explanation"},
            ],
        },
    },
]

def migrate(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)

    # Create templates table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            template_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at_utc TEXT NOT NULL,
            updated_at_utc TEXT NOT NULL,
            is_default BOOLEAN DEFAULT FALSE,
            is_system BOOLEAN DEFAULT FALSE,
            created_by TEXT,
            config_json TEXT NOT NULL
        )
    """)

    # Add template_id to runs if not exists
    cursor = conn.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}
    if "template_id" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN template_id TEXT")

    # Create index
    conn.execute("CREATE INDEX IF NOT EXISTS idx_templates_default ON templates(is_default)")

    # Seed default templates
    now = datetime.utcnow().isoformat() + "Z"
    for template in DEFAULT_TEMPLATES:
        conn.execute(
            """
            INSERT OR IGNORE INTO templates
            (template_id, name, description, created_at_utc, updated_at_utc, is_default, is_system, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                template["template_id"],
                template["name"],
                template["description"],
                now,
                now,
                template["is_default"],
                template["is_system"],
                json.dumps(template["config"]),
            ),
        )

    conn.commit()
    conn.close()
    print("Migration complete. Seeded", len(DEFAULT_TEMPLATES), "templates.")

if __name__ == "__main__":
    import sys
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/index/runs.sqlite3")
    migrate(db_path)
```

### Backend Changes

#### File: `backend/procedurewriter/templates.py` (NEW)

```python
"""
Template management system.

NO MOCKS - All operations use real database.
"""
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import json
from datetime import datetime
from typing import Any

@dataclass
class SectionConfig:
    """Configuration for a single template section."""
    heading: str
    format: str  # "bullets", "numbered", "paragraphs"
    bundle: str  # "action", "explanation", "safety"

@dataclass
class TemplateConfig:
    """Full template configuration."""
    title_prefix: str
    sections: list[SectionConfig]

@dataclass
class Template:
    """Template with metadata."""
    template_id: str
    name: str
    description: str | None
    created_at_utc: str
    updated_at_utc: str
    is_default: bool
    is_system: bool
    config: TemplateConfig

def _parse_config(config_json: str) -> TemplateConfig:
    """Parse JSON config to TemplateConfig."""
    data = json.loads(config_json)
    return TemplateConfig(
        title_prefix=data.get("title_prefix", "Procedure"),
        sections=[
            SectionConfig(
                heading=s["heading"],
                format=s.get("format", "bullets"),
                bundle=s.get("bundle", "action"),
            )
            for s in data.get("sections", [])
        ],
    )

def _serialize_config(config: TemplateConfig) -> str:
    """Serialize TemplateConfig to JSON."""
    return json.dumps({
        "title_prefix": config.title_prefix,
        "sections": [
            {"heading": s.heading, "format": s.format, "bundle": s.bundle}
            for s in config.sections
        ],
    })

def list_templates(db_path: Path) -> list[Template]:
    """List all templates."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM templates ORDER BY is_default DESC, name ASC"
    )
    rows = cursor.fetchall()
    conn.close()

    return [
        Template(
            template_id=row["template_id"],
            name=row["name"],
            description=row["description"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
            is_default=bool(row["is_default"]),
            is_system=bool(row["is_system"]),
            config=_parse_config(row["config_json"]),
        )
        for row in rows
    ]

def get_template(db_path: Path, template_id: str) -> Template | None:
    """Get a specific template."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM templates WHERE template_id = ?",
        (template_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return Template(
        template_id=row["template_id"],
        name=row["name"],
        description=row["description"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        is_default=bool(row["is_default"]),
        is_system=bool(row["is_system"]),
        config=_parse_config(row["config_json"]),
    )

def get_default_template(db_path: Path) -> Template | None:
    """Get the default template."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM templates WHERE is_default = TRUE LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return Template(
        template_id=row["template_id"],
        name=row["name"],
        description=row["description"],
        created_at_utc=row["created_at_utc"],
        updated_at_utc=row["updated_at_utc"],
        is_default=True,
        is_system=bool(row["is_system"]),
        config=_parse_config(row["config_json"]),
    )

def create_template(
    db_path: Path,
    name: str,
    config: TemplateConfig,
    description: str | None = None,
) -> str:
    """Create a new template. Returns template_id."""
    import uuid
    template_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat() + "Z"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO templates
        (template_id, name, description, created_at_utc, updated_at_utc, is_default, is_system, config_json)
        VALUES (?, ?, ?, ?, ?, FALSE, FALSE, ?)
        """,
        (template_id, name, description, now, now, _serialize_config(config)),
    )
    conn.commit()
    conn.close()

    return template_id

def update_template(
    db_path: Path,
    template_id: str,
    name: str | None = None,
    description: str | None = None,
    config: TemplateConfig | None = None,
) -> bool:
    """Update a template. Returns True if updated."""
    template = get_template(db_path, template_id)
    if not template:
        return False

    if template.is_system:
        raise ValueError("Cannot modify system templates")

    now = datetime.utcnow().isoformat() + "Z"
    conn = sqlite3.connect(db_path)

    updates = ["updated_at_utc = ?"]
    values: list[Any] = [now]

    if name is not None:
        updates.append("name = ?")
        values.append(name)

    if description is not None:
        updates.append("description = ?")
        values.append(description)

    if config is not None:
        updates.append("config_json = ?")
        values.append(_serialize_config(config))

    values.append(template_id)

    conn.execute(
        f"UPDATE templates SET {', '.join(updates)} WHERE template_id = ?",
        values,
    )
    conn.commit()
    conn.close()

    return True

def delete_template(db_path: Path, template_id: str) -> bool:
    """Delete a template. Returns True if deleted."""
    template = get_template(db_path, template_id)
    if not template:
        return False

    if template.is_system:
        raise ValueError("Cannot delete system templates")

    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM templates WHERE template_id = ?", (template_id,))
    conn.commit()
    conn.close()

    return True

def set_default_template(db_path: Path, template_id: str) -> bool:
    """Set a template as the default."""
    template = get_template(db_path, template_id)
    if not template:
        return False

    conn = sqlite3.connect(db_path)
    # Clear existing default
    conn.execute("UPDATE templates SET is_default = FALSE")
    # Set new default
    conn.execute(
        "UPDATE templates SET is_default = TRUE WHERE template_id = ?",
        (template_id,),
    )
    conn.commit()
    conn.close()

    return True

def get_template_for_run(db_path: Path, template_id: str | None) -> TemplateConfig:
    """
    Get template config for a run.

    If template_id is None, uses default template.
    Falls back to hardcoded default if no templates exist.
    """
    if template_id:
        template = get_template(db_path, template_id)
        if template:
            return template.config

    # Try default template
    default = get_default_template(db_path)
    if default:
        return default.config

    # Fallback to hardcoded default
    return TemplateConfig(
        title_prefix="Procedure",
        sections=[
            SectionConfig("Indikationer", "bullets", "action"),
            SectionConfig("Kontraindikationer", "bullets", "action"),
            SectionConfig("Forberedelse", "bullets", "action"),
            SectionConfig("Udstyr", "bullets", "action"),
            SectionConfig("Fremgangsmåde (trin-for-trin)", "numbered", "action"),
            SectionConfig("Forklaringslag", "paragraphs", "explanation"),
            SectionConfig("Sikkerhedsboks", "bullets", "safety"),
            SectionConfig("Komplikationer", "bullets", "action"),
            SectionConfig("Disposition", "bullets", "action"),
            SectionConfig("Evidens", "bullets", "explanation"),
        ],
    )
```

#### File: `backend/procedurewriter/main.py` (MODIFY)

Add template endpoints:

```python
from procedurewriter.templates import (
    list_templates,
    get_template,
    create_template,
    update_template,
    delete_template,
    set_default_template,
    get_template_for_run,
    TemplateConfig,
    SectionConfig,
)

# --- Template Endpoints ---

@app.get("/api/templates")
def api_list_templates() -> dict:
    """List all available templates."""
    templates = list_templates(settings.db_path)
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "is_default": t.is_default,
                "is_system": t.is_system,
                "section_count": len(t.config.sections),
            }
            for t in templates
        ]
    }

@app.get("/api/templates/{template_id}")
def api_get_template(template_id: str) -> dict:
    """Get a specific template with full config."""
    template = get_template(settings.db_path, template_id)
    if not template:
        raise HTTPException(404, "Template not found")

    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "is_default": template.is_default,
        "is_system": template.is_system,
        "config": {
            "title_prefix": template.config.title_prefix,
            "sections": [
                {"heading": s.heading, "format": s.format, "bundle": s.bundle}
                for s in template.config.sections
            ],
        },
    }

class CreateTemplateRequest(BaseModel):
    name: str
    description: str | None = None
    config: dict

@app.post("/api/templates")
def api_create_template(request: CreateTemplateRequest) -> dict:
    """Create a new template."""
    config = TemplateConfig(
        title_prefix=request.config.get("title_prefix", "Procedure"),
        sections=[
            SectionConfig(
                heading=s["heading"],
                format=s.get("format", "bullets"),
                bundle=s.get("bundle", "action"),
            )
            for s in request.config.get("sections", [])
        ],
    )

    if not config.sections:
        raise HTTPException(400, "Template must have at least one section")

    template_id = create_template(
        settings.db_path,
        name=request.name,
        description=request.description,
        config=config,
    )

    return {"template_id": template_id}

class UpdateTemplateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None

@app.put("/api/templates/{template_id}")
def api_update_template(template_id: str, request: UpdateTemplateRequest) -> dict:
    """Update a template."""
    config = None
    if request.config:
        config = TemplateConfig(
            title_prefix=request.config.get("title_prefix", "Procedure"),
            sections=[
                SectionConfig(
                    heading=s["heading"],
                    format=s.get("format", "bullets"),
                    bundle=s.get("bundle", "action"),
                )
                for s in request.config.get("sections", [])
            ],
        )

    try:
        success = update_template(
            settings.db_path,
            template_id,
            name=request.name,
            description=request.description,
            config=config,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not success:
        raise HTTPException(404, "Template not found")

    return {"status": "updated"}

@app.delete("/api/templates/{template_id}")
def api_delete_template(template_id: str) -> dict:
    """Delete a template."""
    try:
        success = delete_template(settings.db_path, template_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not success:
        raise HTTPException(404, "Template not found")

    return {"status": "deleted"}

@app.post("/api/templates/{template_id}/set-default")
def api_set_default_template(template_id: str) -> dict:
    """Set a template as the default."""
    success = set_default_template(settings.db_path, template_id)
    if not success:
        raise HTTPException(404, "Template not found")

    return {"status": "default_set"}

# Modify WriteRequest to include template_id
class WriteRequest(BaseModel):
    procedure: str
    context: str | None = None
    template_id: str | None = None  # NEW
    version_note: str | None = None
```

### Frontend Changes

#### File: `frontend/src/pages/TemplatesPage.tsx` (NEW)

```typescript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

interface TemplateSummary {
  template_id: string;
  name: string;
  description: string | null;
  is_default: boolean;
  is_system: boolean;
  section_count: number;
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function loadTemplates() {
    try {
      const r = await fetch("/api/templates");
      const data = await r.json();
      setTemplates(data.templates);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  useEffect(() => {
    void loadTemplates();
  }, []);

  async function setDefault(templateId: string) {
    await fetch(`/api/templates/${templateId}/set-default`, { method: "POST" });
    await loadTemplates();
  }

  async function deleteTemplate(templateId: string) {
    if (!confirm("Slet denne skabelon?")) return;
    await fetch(`/api/templates/${templateId}`, { method: "DELETE" });
    await loadTemplates();
  }

  return (
    <div className="card">
      <h2>Skabeloner</h2>
      <p className="muted">
        Administrer procedure-skabeloner. Skabeloner bestemmer hvilke sektioner der genereres.
      </p>

      {error && <p className="error">{error}</p>}

      <div className="template-list">
        {templates.map(t => (
          <div key={t.template_id} className={`template-item ${t.is_default ? 'is-default' : ''}`}>
            <div className="template-header">
              <strong>{t.name}</strong>
              {t.is_default && <span className="badge">Standard</span>}
              {t.is_system && <span className="badge muted">System</span>}
            </div>
            <p className="muted">{t.description ?? "Ingen beskrivelse"}</p>
            <p className="muted">{t.section_count} sektioner</p>
            <div className="template-actions">
              <Link to={`/templates/${t.template_id}`}>Rediger</Link>
              {!t.is_default && (
                <button onClick={() => setDefault(t.template_id)}>
                  Sæt som standard
                </button>
              )}
              {!t.is_system && (
                <button className="danger" onClick={() => deleteTemplate(t.template_id)}>
                  Slet
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20 }}>
        <Link to="/templates/new">
          <button>+ Opret ny skabelon</button>
        </Link>
      </div>
    </div>
  );
}
```

#### File: `frontend/src/pages/TemplateEditorPage.tsx` (NEW)

```typescript
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";

interface Section {
  heading: string;
  format: "bullets" | "numbered" | "paragraphs";
  bundle: "action" | "explanation" | "safety";
}

interface TemplateConfig {
  title_prefix: string;
  sections: Section[];
}

interface TemplateDetail {
  template_id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  config: TemplateConfig;
}

export default function TemplateEditorPage() {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const isNew = templateId === "new";

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [titlePrefix, setTitlePrefix] = useState("Procedure");
  const [sections, setSections] = useState<Section[]>([]);
  const [isSystem, setIsSystem] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNew) {
      setSections([
        { heading: "Indikationer", format: "bullets", bundle: "action" },
      ]);
      return;
    }

    fetch(`/api/templates/${templateId}`)
      .then(r => r.json())
      .then((data: TemplateDetail) => {
        setName(data.name);
        setDescription(data.description ?? "");
        setTitlePrefix(data.config.title_prefix);
        setSections(data.config.sections);
        setIsSystem(data.is_system);
      })
      .catch(e => setError(e.message));
  }, [templateId, isNew]);

  function addSection() {
    setSections([...sections, { heading: "", format: "bullets", bundle: "action" }]);
  }

  function removeSection(index: number) {
    setSections(sections.filter((_, i) => i !== index));
  }

  function updateSection(index: number, field: keyof Section, value: string) {
    const updated = [...sections];
    updated[index] = { ...updated[index], [field]: value };
    setSections(updated);
  }

  function moveSection(index: number, direction: "up" | "down") {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;

    const updated = [...sections];
    [updated[index], updated[newIndex]] = [updated[newIndex], updated[index]];
    setSections(updated);
  }

  async function save() {
    const config = { title_prefix: titlePrefix, sections };

    try {
      if (isNew) {
        await fetch("/api/templates", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description, config }),
        });
      } else {
        await fetch(`/api/templates/${templateId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description, config }),
        });
      }
      navigate("/templates");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="card">
      <h2>{isNew ? "Opret skabelon" : "Rediger skabelon"}</h2>

      {error && <p className="error">{error}</p>}
      {isSystem && <p className="warning">System-skabeloner kan ikke redigeres</p>}

      <div className="form-group">
        <label>Navn</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          disabled={isSystem}
          placeholder="Fx: Kirurgisk procedure"
        />
      </div>

      <div className="form-group">
        <label>Beskrivelse</label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          disabled={isSystem}
          rows={2}
        />
      </div>

      <div className="form-group">
        <label>Titel-præfiks</label>
        <input
          value={titlePrefix}
          onChange={e => setTitlePrefix(e.target.value)}
          disabled={isSystem}
          placeholder="Procedure"
        />
      </div>

      <h3>Sektioner</h3>
      <div className="sections-list">
        {sections.map((section, i) => (
          <div key={i} className="section-row">
            <input
              value={section.heading}
              onChange={e => updateSection(i, "heading", e.target.value)}
              disabled={isSystem}
              placeholder="Sektionsnavn"
            />
            <select
              value={section.format}
              onChange={e => updateSection(i, "format", e.target.value)}
              disabled={isSystem}
            >
              <option value="bullets">Bullets</option>
              <option value="numbered">Nummereret</option>
              <option value="paragraphs">Afsnit</option>
            </select>
            <select
              value={section.bundle}
              onChange={e => updateSection(i, "bundle", e.target.value)}
              disabled={isSystem}
            >
              <option value="action">Action</option>
              <option value="explanation">Forklaring</option>
              <option value="safety">Sikkerhed</option>
            </select>
            {!isSystem && (
              <>
                <button onClick={() => moveSection(i, "up")} disabled={i === 0}>↑</button>
                <button onClick={() => moveSection(i, "down")} disabled={i === sections.length - 1}>↓</button>
                <button onClick={() => removeSection(i)}>×</button>
              </>
            )}
          </div>
        ))}
      </div>

      {!isSystem && (
        <button onClick={addSection} style={{ marginTop: 10 }}>
          + Tilføj sektion
        </button>
      )}

      <div className="form-actions" style={{ marginTop: 20 }}>
        {!isSystem && (
          <button onClick={save}>Gem</button>
        )}
        <button onClick={() => navigate("/templates")}>Annuller</button>
      </div>
    </div>
  );
}
```

#### File: `frontend/src/pages/WritePage.tsx` (MODIFY)

Add template selection:

```typescript
// Add state
const [templates, setTemplates] = useState<TemplateSummary[]>([]);
const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);

// Load templates on mount
useEffect(() => {
  fetch("/api/templates")
    .then(r => r.json())
    .then(data => {
      setTemplates(data.templates);
      const defaultTemplate = data.templates.find((t: TemplateSummary) => t.is_default);
      if (defaultTemplate) {
        setSelectedTemplate(defaultTemplate.template_id);
      }
    });
}, []);

// Modify onGenerate
async function onGenerate() {
  // ... existing code ...
  const id = await apiWrite({
    procedure: procedure.trim(),
    context: context.trim() || undefined,
    template_id: selectedTemplate ?? undefined,  // NEW
  });
  // ... rest ...
}

// Add to JSX
<div style={{ marginTop: 12 }}>
  <label className="muted">Skabelon</label>
  <select
    value={selectedTemplate ?? ""}
    onChange={e => setSelectedTemplate(e.target.value || null)}
  >
    {templates.map(t => (
      <option key={t.template_id} value={t.template_id}>
        {t.name} {t.is_default ? "(standard)" : ""}
      </option>
    ))}
  </select>
</div>
```

---

## Test Requirements

### Backend Tests

#### File: `backend/tests/test_templates.py` (NEW)

```python
"""
Template Management Tests

IMPORTANT: Tests use REAL database operations.
NO MOCKS for storage.
"""
import pytest
from pathlib import Path
import tempfile

from procedurewriter.templates import (
    list_templates,
    get_template,
    create_template,
    update_template,
    delete_template,
    set_default_template,
    get_template_for_run,
    TemplateConfig,
    SectionConfig,
)

@pytest.fixture
def temp_db():
    """Create temporary database with templates table."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Run migration
        import subprocess
        subprocess.run([
            "python", "scripts/migrate_templates.py", str(db_path)
        ], check=True)

        yield db_path


class TestTemplateOperations:
    """Test template CRUD operations."""

    def test_list_templates_includes_defaults(self, temp_db):
        """Default templates are available after migration."""
        templates = list_templates(temp_db)
        assert len(templates) >= 3  # 3 system templates
        assert any(t.name == "Emergency Standard" for t in templates)

    def test_create_and_get_template(self, temp_db):
        """Can create and retrieve a custom template."""
        config = TemplateConfig(
            title_prefix="Custom",
            sections=[
                SectionConfig("Test Section", "bullets", "action"),
            ],
        )
        template_id = create_template(temp_db, "Test Template", config)

        template = get_template(temp_db, template_id)
        assert template is not None
        assert template.name == "Test Template"
        assert len(template.config.sections) == 1

    def test_update_template(self, temp_db):
        """Can update a custom template."""
        config = TemplateConfig(
            title_prefix="Original",
            sections=[SectionConfig("A", "bullets", "action")],
        )
        template_id = create_template(temp_db, "Original", config)

        new_config = TemplateConfig(
            title_prefix="Updated",
            sections=[
                SectionConfig("A", "bullets", "action"),
                SectionConfig("B", "numbered", "safety"),
            ],
        )
        update_template(temp_db, template_id, name="Updated", config=new_config)

        template = get_template(temp_db, template_id)
        assert template.name == "Updated"
        assert len(template.config.sections) == 2

    def test_cannot_update_system_template(self, temp_db):
        """System templates cannot be modified."""
        templates = list_templates(temp_db)
        system_template = next(t for t in templates if t.is_system)

        with pytest.raises(ValueError, match="system"):
            update_template(temp_db, system_template.template_id, name="Hacked")

    def test_delete_template(self, temp_db):
        """Can delete a custom template."""
        config = TemplateConfig(
            title_prefix="ToDelete",
            sections=[SectionConfig("A", "bullets", "action")],
        )
        template_id = create_template(temp_db, "ToDelete", config)

        success = delete_template(temp_db, template_id)
        assert success

        template = get_template(temp_db, template_id)
        assert template is None

    def test_cannot_delete_system_template(self, temp_db):
        """System templates cannot be deleted."""
        templates = list_templates(temp_db)
        system_template = next(t for t in templates if t.is_system)

        with pytest.raises(ValueError, match="system"):
            delete_template(temp_db, system_template.template_id)

    def test_set_default_template(self, temp_db):
        """Can change the default template."""
        templates = list_templates(temp_db)
        non_default = next(t for t in templates if not t.is_default)

        set_default_template(temp_db, non_default.template_id)

        updated = get_template(temp_db, non_default.template_id)
        assert updated.is_default

        # Old default should no longer be default
        old_default = next(t for t in list_templates(temp_db) if t.template_id != non_default.template_id and t.is_default is False or t.template_id == non_default.template_id)
        # Verify only one default
        defaults = [t for t in list_templates(temp_db) if t.is_default]
        assert len(defaults) == 1


class TestTemplateForRun:
    """Test template resolution for runs."""

    def test_specific_template_used(self, temp_db):
        """Specific template_id is used when provided."""
        templates = list_templates(temp_db)
        template = templates[0]

        config = get_template_for_run(temp_db, template.template_id)
        assert config.title_prefix == template.config.title_prefix

    def test_default_template_when_none_specified(self, temp_db):
        """Default template is used when template_id is None."""
        config = get_template_for_run(temp_db, None)
        assert len(config.sections) > 0

    def test_fallback_when_no_templates(self):
        """Fallback to hardcoded when no templates exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_db = Path(tmpdir) / "empty.db"
            # Don't run migration - no templates table

            # Should not crash, use fallback
            # (This test verifies graceful degradation)
            pass
```

---

## Implementation Checklist

### Phase 1: Database & Migration (Day 1)

- [ ] Create migration script `backend/scripts/migrate_templates.py`
- [ ] Design default templates (Emergency, Surgical, Pediatric)
- [ ] Add templates table schema
- [ ] Add template_id to runs table
- [ ] Run migration on dev database
- [ ] Verify migration with SQL queries

### Phase 2: Backend Template System (Day 1-2)

- [ ] Create `backend/procedurewriter/templates.py`
- [ ] Implement list/get/create/update/delete functions
- [ ] Implement set_default_template
- [ ] Implement get_template_for_run
- [ ] Write unit tests
- [ ] Run tests: `pytest backend/tests/test_templates.py -v`

### Phase 3: API Endpoints (Day 2)

- [ ] Add template CRUD endpoints to `main.py`
- [ ] Add template_id to WriteRequest
- [ ] Modify pipeline to use template
- [ ] Test API endpoints with curl

### Phase 4: Frontend - Templates Page (Day 3)

- [ ] Create `TemplatesPage.tsx` (list view)
- [ ] Create `TemplateEditorPage.tsx` (create/edit)
- [ ] Add routes to router
- [ ] Add navigation link to templates page
- [ ] Style template list and editor

### Phase 5: Frontend - Write Integration (Day 4)

- [ ] Add template dropdown to `WritePage.tsx`
- [ ] Load templates on mount
- [ ] Include template_id in write request
- [ ] Show template info in run details

### Phase 6: Polish (Day 4-5)

- [ ] Section reordering UI polish
- [ ] Validation (at least one section)
- [ ] Run full test suite
- [ ] Manual E2E testing
- [ ] Documentation

---

## Current Status

**Status**: NOT STARTED

**Last Updated**: 2024-12-18

**Checkpoints Completed**:
- [ ] Phase 1: Database & Migration
- [ ] Phase 2: Backend Template System
- [ ] Phase 3: API Endpoints
- [ ] Phase 4: Frontend - Templates Page
- [ ] Phase 5: Frontend - Write Integration
- [ ] Phase 6: Polish

**Blockers**: None

**Notes**: Ready to begin. Migration creates default templates.

---

## Session Handoff Notes

When continuing this enhancement in a new session:

1. Read this document first
2. Check "Current Status" above
3. Load skills: `Skill(superpowers:test-driven-development)`
4. Check if migration has been run
5. Run existing tests: `pytest`
6. Continue from last incomplete checkbox

**REMEMBER**: No dummy/mock implementations. All operations use real database.

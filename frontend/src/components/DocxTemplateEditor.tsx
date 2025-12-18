import { useState, useEffect, useCallback } from "react";

// Types for the template structure
interface Section {
  id: string;
  heading: string;
  visible: boolean;
  format: string;
}

interface FontConfig {
  family: string;
  size: number;
  bold?: boolean;
}

interface DocxTemplate {
  structure: {
    sections: Section[];
  };
  styling: {
    fonts: {
      body: FontConfig;
      heading1: FontConfig;
      heading2: FontConfig;
    };
    colors: {
      heading1: string;
      heading2: string;
      body: string;
      citation: string;
      safety_box_background: string;
    };
  };
  content: {
    citations: {
      style: string;
      size: number;
      show_references: boolean;
    };
    evidence_badges: {
      show_in_text: boolean;
      show_in_references: boolean;
    };
    audit_trail: {
      show: boolean;
      abbreviated_hash: boolean;
    };
    page_numbers: {
      show: boolean;
      format: string;
    };
    quality_score?: {
      show: boolean;
    };
  };
}

// Preset configurations
const presets: Record<string, Partial<DocxTemplate>> = {
  standard: {
    content: {
      citations: { style: "superscript", size: 8, show_references: true },
      evidence_badges: { show_in_text: false, show_in_references: true },
      audit_trail: { show: true, abbreviated_hash: true },
      page_numbers: { show: true, format: "Side X af Y" },
      quality_score: { show: false },
    },
  },
  minimal: {
    content: {
      citations: { style: "superscript", size: 8, show_references: false },
      evidence_badges: { show_in_text: false, show_in_references: false },
      audit_trail: { show: false, abbreviated_hash: true },
      page_numbers: { show: true, format: "X" },
      quality_score: { show: false },
    },
  },
  detailed: {
    content: {
      citations: { style: "footnote", size: 9, show_references: true },
      evidence_badges: { show_in_text: true, show_in_references: true },
      audit_trail: { show: true, abbreviated_hash: false },
      page_numbers: { show: true, format: "Side X af Y" },
      quality_score: { show: true },
    },
  },
};

// Color presets
const colorPresets = {
  heading: ["#003366", "#1a365d", "#2c5282", "#234e52", "#553c9a", "#702459"],
  body: ["#000000", "#1a202c", "#2d3748", "#4a5568"],
  citation: ["#6e6e6e", "#718096", "#a0aec0", "#4a5568"],
  safety: ["#FFF2CC", "#FEEBC8", "#FED7D7", "#C6F6D5", "#BEE3F8"],
};

// Default template
const defaultTemplate: DocxTemplate = {
  structure: {
    sections: [
      { id: "indikation", heading: "Indikation", visible: true, format: "bullets" },
      { id: "kontraindikation", heading: "Kontraindikation", visible: true, format: "bullets" },
      { id: "udstyr", heading: "Udstyr", visible: true, format: "bullets" },
      { id: "forberedelse", heading: "Forberedelse", visible: true, format: "numbered" },
      { id: "procedure", heading: "Procedure", visible: true, format: "numbered" },
      { id: "sikkerhedsboks", heading: "Sikkerhedsboks", visible: true, format: "safety_box" },
      { id: "komplikationer", heading: "Komplikationer", visible: true, format: "bullets" },
      { id: "efterbehandling", heading: "Efterbehandling", visible: true, format: "bullets" },
      { id: "dokumentation", heading: "Dokumentation", visible: true, format: "bullets" },
      { id: "referencer", heading: "Referencer", visible: true, format: "references" },
    ],
  },
  styling: {
    fonts: {
      body: { family: "Calibri", size: 11 },
      heading1: { family: "Calibri", size: 16, bold: true },
      heading2: { family: "Calibri", size: 14, bold: true },
    },
    colors: {
      heading1: "#003366",
      heading2: "#003366",
      body: "#000000",
      citation: "#6e6e6e",
      safety_box_background: "#FFF2CC",
    },
  },
  content: {
    citations: { style: "superscript", size: 8, show_references: true },
    evidence_badges: { show_in_text: false, show_in_references: true },
    audit_trail: { show: true, abbreviated_hash: true },
    page_numbers: { show: true, format: "Side X af Y" },
    quality_score: { show: false },
  },
};

// Section icons
const sectionIcons: Record<string, string> = {
  indikation: "🎯",
  kontraindikation: "⛔",
  udstyr: "🔧",
  forberedelse: "📋",
  procedure: "📝",
  sikkerhedsboks: "⚠️",
  komplikationer: "🚨",
  efterbehandling: "💊",
  dokumentation: "📄",
  referencer: "📚",
};

// Parse YAML-ish text to template object
function parseTemplate(yamlText: string): DocxTemplate {
  try {
    const template = JSON.parse(JSON.stringify(defaultTemplate));

    // Extract sections
    const sectionsMatch = yamlText.match(/sections:\s*\n([\s\S]*?)(?=\n\w|$)/);
    if (sectionsMatch) {
      const sectionsBlock = sectionsMatch[1];
      const sectionMatches = sectionsBlock.matchAll(
        /- id: (\w+)\s*\n\s*heading: "?([^"\n]+)"?\s*\n\s*visible: (true|false)\s*\n\s*format: (\w+)/g
      );
      const sections: Section[] = [];
      for (const match of sectionMatches) {
        sections.push({
          id: match[1],
          heading: match[2],
          visible: match[3] === "true",
          format: match[4],
        });
      }
      if (sections.length > 0) {
        template.structure.sections = sections;
      }
    }

    // Extract colors
    const colorPatterns = [
      { key: "heading1", pattern: /heading1:\s*"?(#[0-9a-fA-F]{6})"?/ },
      { key: "heading2", pattern: /heading2:\s*"?(#[0-9a-fA-F]{6})"?/ },
      { key: "body", pattern: /body:\s*"?(#[0-9a-fA-F]{6})"?/ },
      { key: "citation", pattern: /citation:\s*"?(#[0-9a-fA-F]{6})"?/ },
      { key: "safety_box_background", pattern: /safety_box_background:\s*"?(#[0-9a-fA-F]{6})"?/ },
    ];
    for (const { key, pattern } of colorPatterns) {
      const match = yamlText.match(pattern);
      if (match) {
        (template.styling.colors as Record<string, string>)[key] = match[1];
      }
    }

    // Extract booleans
    const boolPatterns = [
      { path: ["content", "citations", "show_references"], pattern: /show_references:\s*(true|false)/ },
      { path: ["content", "evidence_badges", "show_in_text"], pattern: /show_in_text:\s*(true|false)/ },
      { path: ["content", "evidence_badges", "show_in_references"], pattern: /show_in_references:\s*(true|false)/ },
      { path: ["content", "audit_trail", "show"], pattern: /audit_trail:[\s\S]*?show:\s*(true|false)/ },
      { path: ["content", "audit_trail", "abbreviated_hash"], pattern: /abbreviated_hash:\s*(true|false)/ },
      { path: ["content", "page_numbers", "show"], pattern: /page_numbers:[\s\S]*?show:\s*(true|false)/ },
    ];
    for (const { path, pattern } of boolPatterns) {
      const match = yamlText.match(pattern);
      if (match) {
        let obj: Record<string, unknown> = template as unknown as Record<string, unknown>;
        for (let i = 0; i < path.length - 1; i++) {
          obj = obj[path[i]] as Record<string, unknown>;
        }
        obj[path[path.length - 1]] = match[1] === "true";
      }
    }

    return template;
  } catch {
    return defaultTemplate;
  }
}

// Convert template object to YAML text
function templateToYaml(template: DocxTemplate): string {
  const lines: string[] = [
    "# DOCX Template Configuration",
    "version: 1",
    "",
    "structure:",
    "  sections:",
  ];

  for (const section of template.structure.sections) {
    lines.push(`    - id: ${section.id}`);
    lines.push(`      heading: "${section.heading}"`);
    lines.push(`      visible: ${section.visible}`);
    lines.push(`      format: ${section.format}`);
  }

  lines.push("");
  lines.push("styling:");
  lines.push("  fonts:");
  lines.push(`    body:`);
  lines.push(`      family: ${template.styling.fonts.body.family}`);
  lines.push(`      size: ${template.styling.fonts.body.size}`);
  lines.push(`    heading1:`);
  lines.push(`      family: ${template.styling.fonts.heading1.family}`);
  lines.push(`      size: ${template.styling.fonts.heading1.size}`);
  lines.push(`      bold: true`);
  lines.push(`    heading2:`);
  lines.push(`      family: ${template.styling.fonts.heading2.family}`);
  lines.push(`      size: ${template.styling.fonts.heading2.size}`);
  lines.push(`      bold: true`);
  lines.push("  colors:");
  lines.push(`    heading1: "${template.styling.colors.heading1}"`);
  lines.push(`    heading2: "${template.styling.colors.heading2}"`);
  lines.push(`    body: "${template.styling.colors.body}"`);
  lines.push(`    citation: "${template.styling.colors.citation}"`);
  lines.push(`    safety_box_background: "${template.styling.colors.safety_box_background}"`);

  lines.push("");
  lines.push("content:");
  lines.push("  citations:");
  lines.push(`    style: ${template.content.citations.style}`);
  lines.push(`    size: ${template.content.citations.size}`);
  lines.push(`    show_references: ${template.content.citations.show_references}`);
  lines.push("  evidence_badges:");
  lines.push(`    show_in_text: ${template.content.evidence_badges.show_in_text}`);
  lines.push(`    show_in_references: ${template.content.evidence_badges.show_in_references}`);
  lines.push("  audit_trail:");
  lines.push(`    show: ${template.content.audit_trail.show}`);
  lines.push(`    abbreviated_hash: ${template.content.audit_trail.abbreviated_hash}`);
  lines.push("  page_numbers:");
  lines.push(`    show: ${template.content.page_numbers.show}`);
  lines.push(`    format: "${template.content.page_numbers.format}"`);
  if (template.content.quality_score) {
    lines.push("  quality_score:");
    lines.push(`    show: ${template.content.quality_score.show}`);
  }

  return lines.join("\n");
}

// Toggle Switch Component
function Toggle({
  checked,
  onChange,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      style={{
        position: "relative",
        width: 44,
        height: 24,
        borderRadius: 12,
        border: "none",
        background: checked ? "#4299e1" : "#4a5568",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 0.2s",
        opacity: disabled ? 0.5 : 1,
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: checked ? 22 : 2,
          width: 20,
          height: 20,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 0.2s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        }}
      />
    </button>
  );
}

// Setting Card Component
function SettingCard({
  icon,
  title,
  description,
  children,
}: {
  icon: string;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background: "linear-gradient(135deg, #1a2a4a 0%, #152238 100%)",
        borderRadius: 12,
        padding: 20,
        border: "1px solid #2d3e5f",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 20 }}>{icon}</span>
        <div>
          <h4 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#e2e8f0" }}>{title}</h4>
          {description && (
            <p style={{ margin: 0, fontSize: 12, color: "#718096", marginTop: 2 }}>{description}</p>
          )}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>{children}</div>
    </div>
  );
}

// Setting Row Component
function SettingRow({
  label,
  tooltip,
  children,
}: {
  label: string;
  tooltip?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "8px 0",
        borderBottom: "1px solid #2d3e5f22",
      }}
      title={tooltip}
    >
      <span style={{ color: "#cbd5e0", fontSize: 14 }}>{label}</span>
      {children}
    </div>
  );
}

// Color Picker with Presets
function ColorPickerWithPresets({
  value,
  onChange,
  presetColors,
}: {
  value: string;
  onChange: (color: string) => void;
  presetColors: string[];
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ display: "flex", gap: 4 }}>
        {presetColors.slice(0, 4).map((color) => (
          <button
            key={color}
            onClick={() => onChange(color)}
            style={{
              width: 20,
              height: 20,
              borderRadius: 4,
              border: value === color ? "2px solid #4299e1" : "1px solid #4a5568",
              background: color,
              cursor: "pointer",
              padding: 0,
            }}
            title={color}
          />
        ))}
      </div>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          width: 32,
          height: 24,
          padding: 0,
          border: "none",
          borderRadius: 4,
          cursor: "pointer",
        }}
      />
      <code style={{ fontSize: 11, color: "#718096", minWidth: 60 }}>{value}</code>
    </div>
  );
}

// Font Selector with Preview
function FontSelector({
  family,
  size,
  onFamilyChange,
  onSizeChange,
  label,
}: {
  family: string;
  size: number;
  onFamilyChange: (f: string) => void;
  onSizeChange: (s: number) => void;
  label: string;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <label style={{ fontSize: 12, color: "#718096" }}>{label}</label>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <select
          value={family}
          onChange={(e) => onFamilyChange(e.target.value)}
          style={{
            flex: 1,
            padding: "8px 12px",
            background: "#0d1520",
            border: "1px solid #2d3e5f",
            borderRadius: 6,
            color: "#e2e8f0",
            fontSize: 13,
          }}
        >
          <option value="Calibri">Calibri</option>
          <option value="Arial">Arial</option>
          <option value="Times New Roman">Times New Roman</option>
          <option value="Georgia">Georgia</option>
          <option value="Verdana">Verdana</option>
          <option value="Helvetica">Helvetica</option>
        </select>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          <input
            type="number"
            value={size}
            onChange={(e) => onSizeChange(parseInt(e.target.value) || 11)}
            min={8}
            max={36}
            style={{
              width: 56,
              padding: "8px",
              background: "#0d1520",
              border: "1px solid #2d3e5f",
              borderRadius: 6,
              color: "#e2e8f0",
              fontSize: 13,
              textAlign: "center",
            }}
          />
          <span style={{ color: "#718096", fontSize: 12 }}>pt</span>
        </div>
      </div>
      <div
        style={{
          padding: "8px 12px",
          background: "#0d1520",
          borderRadius: 6,
          fontFamily: family,
          fontSize: size,
          color: "#e2e8f0",
          minHeight: 24,
        }}
      >
        Eksempel tekst Aa Bb 123
      </div>
    </div>
  );
}

interface Props {
  yamlText: string;
  onChange: (yaml: string) => void;
  onSave: () => void;
  saving: boolean;
}

export default function DocxTemplateEditor({ yamlText, onChange, onSave, saving }: Props) {
  const [template, setTemplate] = useState<DocxTemplate>(() => parseTemplate(yamlText));
  const [activeTab, setActiveTab] = useState<"sections" | "styling" | "content">("sections");
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  useEffect(() => {
    setTemplate(parseTemplate(yamlText));
  }, [yamlText]);

  const updateTemplate = useCallback(
    (newTemplate: DocxTemplate) => {
      setTemplate(newTemplate);
      onChange(templateToYaml(newTemplate));
    },
    [onChange]
  );

  const applyPreset = (presetName: string) => {
    const preset = presets[presetName];
    if (preset) {
      updateTemplate({
        ...template,
        content: { ...template.content, ...preset.content },
      });
    }
  };

  const resetToDefaults = () => {
    updateTemplate(defaultTemplate);
  };

  const moveSection = (index: number, direction: "up" | "down") => {
    const sections = [...template.structure.sections];
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;
    [sections[index], sections[newIndex]] = [sections[newIndex], sections[index]];
    updateTemplate({ ...template, structure: { ...template.structure, sections } });
  };

  const toggleSection = (index: number) => {
    const sections = [...template.structure.sections];
    sections[index] = { ...sections[index], visible: !sections[index].visible };
    updateTemplate({ ...template, structure: { ...template.structure, sections } });
  };

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const sections = [...template.structure.sections];
    const draggedSection = sections[draggedIndex];
    sections.splice(draggedIndex, 1);
    sections.splice(index, 0, draggedSection);

    setDraggedIndex(index);
    updateTemplate({ ...template, structure: { ...template.structure, sections } });
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const updateColor = (key: keyof DocxTemplate["styling"]["colors"], value: string) => {
    updateTemplate({
      ...template,
      styling: {
        ...template.styling,
        colors: { ...template.styling.colors, [key]: value },
      },
    });
  };

  const updateFont = (key: keyof DocxTemplate["styling"]["fonts"], prop: "family" | "size", value: string | number) => {
    updateTemplate({
      ...template,
      styling: {
        ...template.styling,
        fonts: {
          ...template.styling.fonts,
          [key]: { ...template.styling.fonts[key], [prop]: value },
        },
      },
    });
  };

  const tabs = [
    { id: "sections" as const, label: "Sektioner", icon: "📑" },
    { id: "styling" as const, label: "Styling", icon: "🎨" },
    { id: "content" as const, label: "Indhold", icon: "📝" },
  ];

  return (
    <div style={{ marginTop: 8 }}>
      {/* Header with Presets */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 20,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <label style={{ color: "#718096", fontSize: 13 }}>Hurtig opsætning:</label>
          <select
            onChange={(e) => e.target.value && applyPreset(e.target.value)}
            defaultValue=""
            style={{
              padding: "8px 12px",
              background: "#0d1520",
              border: "1px solid #2d3e5f",
              borderRadius: 6,
              color: "#e2e8f0",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            <option value="" disabled>
              Vælg preset...
            </option>
            <option value="standard">📋 Standard (anbefalet)</option>
            <option value="minimal">📄 Minimal</option>
            <option value="detailed">📊 Detaljeret</option>
          </select>
        </div>
        <button
          onClick={resetToDefaults}
          style={{
            padding: "8px 16px",
            background: "transparent",
            border: "1px solid #4a5568",
            borderRadius: 6,
            color: "#a0aec0",
            fontSize: 13,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          ↺ Nulstil til standard
        </button>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 20,
          borderBottom: "2px solid #1a2a4a",
          paddingBottom: 0,
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "12px 20px",
              background: activeTab === tab.id ? "#1a2a4a" : "transparent",
              border: "none",
              borderRadius: "8px 8px 0 0",
              color: activeTab === tab.id ? "#fff" : "#718096",
              cursor: "pointer",
              fontSize: 14,
              fontWeight: activeTab === tab.id ? 600 : 400,
              display: "flex",
              alignItems: "center",
              gap: 8,
              transition: "all 0.2s",
              borderBottom: activeTab === tab.id ? "2px solid #4299e1" : "2px solid transparent",
              marginBottom: -2,
            }}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Sections Tab */}
      {activeTab === "sections" && (
        <div>
          <p style={{ color: "#718096", fontSize: 13, marginBottom: 16 }}>
            Træk for at ændre rækkefølge. Klik på toggles for at vise/skjule sektioner.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {template.structure.sections.map((section, index) => (
              <div
                key={section.id}
                draggable
                onDragStart={() => handleDragStart(index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  padding: "12px 16px",
                  background:
                    draggedIndex === index
                      ? "#2d4a6a"
                      : section.visible
                        ? "linear-gradient(135deg, #1a2a4a 0%, #152238 100%)"
                        : "#0d1520",
                  borderRadius: 10,
                  border: draggedIndex === index ? "2px dashed #4299e1" : "1px solid #2d3e5f",
                  opacity: section.visible ? 1 : 0.6,
                  cursor: "grab",
                  transition: "all 0.2s",
                }}
              >
                <span style={{ cursor: "grab", color: "#4a5568", fontSize: 18 }}>⋮⋮</span>
                <span style={{ fontSize: 20, width: 28 }}>{sectionIcons[section.id] || "📄"}</span>
                <span style={{ flex: 1, fontWeight: 500, color: "#e2e8f0" }}>{section.heading}</span>
                <span
                  style={{
                    fontSize: 11,
                    color: "#718096",
                    background: "#0d1520",
                    padding: "4px 8px",
                    borderRadius: 4,
                  }}
                >
                  {section.format === "bullets" && "• Punkter"}
                  {section.format === "numbered" && "1. Nummereret"}
                  {section.format === "safety_box" && "⚠ Advarsel"}
                  {section.format === "references" && "📚 Referencer"}
                </span>
                <Toggle checked={section.visible} onChange={() => toggleSection(index)} />
                <div style={{ display: "flex", gap: 4 }}>
                  <button
                    onClick={() => moveSection(index, "up")}
                    disabled={index === 0}
                    style={{
                      padding: "6px 10px",
                      background: "#0d1520",
                      border: "1px solid #2d3e5f",
                      borderRadius: 6,
                      color: index === 0 ? "#2d3e5f" : "#a0aec0",
                      cursor: index === 0 ? "not-allowed" : "pointer",
                      fontSize: 12,
                    }}
                  >
                    ▲
                  </button>
                  <button
                    onClick={() => moveSection(index, "down")}
                    disabled={index === template.structure.sections.length - 1}
                    style={{
                      padding: "6px 10px",
                      background: "#0d1520",
                      border: "1px solid #2d3e5f",
                      borderRadius: 6,
                      color: index === template.structure.sections.length - 1 ? "#2d3e5f" : "#a0aec0",
                      cursor: index === template.structure.sections.length - 1 ? "not-allowed" : "pointer",
                      fontSize: 12,
                    }}
                  >
                    ▼
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Styling Tab */}
      {activeTab === "styling" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Fonts Card */}
          <SettingCard icon="🔤" title="Skrifttyper" description="Vælg fonte og størrelser">
            <FontSelector
              label="Brødtekst"
              family={template.styling.fonts.body.family}
              size={template.styling.fonts.body.size}
              onFamilyChange={(f) => updateFont("body", "family", f)}
              onSizeChange={(s) => updateFont("body", "size", s)}
            />
            <FontSelector
              label="Overskrift 1 (H1)"
              family={template.styling.fonts.heading1.family}
              size={template.styling.fonts.heading1.size}
              onFamilyChange={(f) => updateFont("heading1", "family", f)}
              onSizeChange={(s) => updateFont("heading1", "size", s)}
            />
            <FontSelector
              label="Overskrift 2 (H2)"
              family={template.styling.fonts.heading2.family}
              size={template.styling.fonts.heading2.size}
              onFamilyChange={(f) => updateFont("heading2", "family", f)}
              onSizeChange={(s) => updateFont("heading2", "size", s)}
            />
          </SettingCard>

          {/* Colors Card */}
          <SettingCard icon="🎨" title="Farver" description="Tilpas dokumentets farveskema">
            <SettingRow label="Overskrift 1" tooltip="Farve til hovedoverskrifter">
              <ColorPickerWithPresets
                value={template.styling.colors.heading1}
                onChange={(c) => updateColor("heading1", c)}
                presetColors={colorPresets.heading}
              />
            </SettingRow>
            <SettingRow label="Overskrift 2" tooltip="Farve til underoverskrifter">
              <ColorPickerWithPresets
                value={template.styling.colors.heading2}
                onChange={(c) => updateColor("heading2", c)}
                presetColors={colorPresets.heading}
              />
            </SettingRow>
            <SettingRow label="Brødtekst" tooltip="Farve til almindelig tekst">
              <ColorPickerWithPresets
                value={template.styling.colors.body}
                onChange={(c) => updateColor("body", c)}
                presetColors={colorPresets.body}
              />
            </SettingRow>
            <SettingRow label="Citationer" tooltip="Farve til kildehenvisninger">
              <ColorPickerWithPresets
                value={template.styling.colors.citation}
                onChange={(c) => updateColor("citation", c)}
                presetColors={colorPresets.citation}
              />
            </SettingRow>
            <SettingRow label="Sikkerhedsboks" tooltip="Baggrundsfarve til advarsler">
              <ColorPickerWithPresets
                value={template.styling.colors.safety_box_background}
                onChange={(c) => updateColor("safety_box_background", c)}
                presetColors={colorPresets.safety}
              />
            </SettingRow>
          </SettingCard>
        </div>
      )}

      {/* Content Tab */}
      {activeTab === "content" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Citations Card */}
          <SettingCard icon="📖" title="Citationer" description="Hvordan kilder vises i teksten">
            <SettingRow label="Citationsstil">
              <select
                value={template.content.citations.style}
                onChange={(e) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      citations: { ...template.content.citations, style: e.target.value },
                    },
                  })
                }
                style={{
                  padding: "8px 12px",
                  background: "#0d1520",
                  border: "1px solid #2d3e5f",
                  borderRadius: 6,
                  color: "#e2e8f0",
                  fontSize: 13,
                  minWidth: 160,
                }}
              >
                <option value="superscript">Hævet skrift ¹²³</option>
                <option value="inline">Inline [1]</option>
                <option value="footnote">Fodnoter</option>
              </select>
            </SettingRow>
            <SettingRow label="Skriftstørrelse">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="range"
                  min={6}
                  max={12}
                  value={template.content.citations.size}
                  onChange={(e) =>
                    updateTemplate({
                      ...template,
                      content: {
                        ...template.content,
                        citations: { ...template.content.citations, size: parseInt(e.target.value) },
                      },
                    })
                  }
                  style={{ width: 80 }}
                />
                <span style={{ color: "#e2e8f0", minWidth: 40 }}>{template.content.citations.size} pt</span>
              </div>
            </SettingRow>
            <SettingRow label="Vis referenceliste" tooltip="Inkludér liste over kilder til sidst">
              <Toggle
                checked={template.content.citations.show_references}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      citations: { ...template.content.citations, show_references: checked },
                    },
                  })
                }
              />
            </SettingRow>
          </SettingCard>

          {/* Evidence Badges Card */}
          <SettingCard icon="🏷️" title="Evidens-badges" description="Vis evidensniveau for kilder">
            <SettingRow label="Vis i tekst" tooltip="Vis evidensniveau inline i teksten">
              <Toggle
                checked={template.content.evidence_badges.show_in_text}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      evidence_badges: { ...template.content.evidence_badges, show_in_text: checked },
                    },
                  })
                }
              />
            </SettingRow>
            <SettingRow label="Vis i referenceliste" tooltip="Vis evidensniveau ved hver reference">
              <Toggle
                checked={template.content.evidence_badges.show_in_references}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      evidence_badges: { ...template.content.evidence_badges, show_in_references: checked },
                    },
                  })
                }
              />
            </SettingRow>
          </SettingCard>

          {/* Audit Trail Card */}
          <SettingCard icon="🔍" title="Audit Trail" description="Sporbarhed og versionering">
            <SettingRow label="Vis i footer" tooltip="Inkludér audit trail i dokumentets bund">
              <Toggle
                checked={template.content.audit_trail.show}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      audit_trail: { ...template.content.audit_trail, show: checked },
                    },
                  })
                }
              />
            </SettingRow>
            <SettingRow label="Forkortet hash" tooltip="Brug kun de første 8 tegn af hash">
              <Toggle
                checked={template.content.audit_trail.abbreviated_hash}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      audit_trail: { ...template.content.audit_trail, abbreviated_hash: checked },
                    },
                  })
                }
              />
            </SettingRow>
          </SettingCard>

          {/* Page Numbers Card */}
          <SettingCard icon="📄" title="Sidetal" description="Sidetalformat i dokumentet">
            <SettingRow label="Vis sidetal">
              <Toggle
                checked={template.content.page_numbers.show}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      page_numbers: { ...template.content.page_numbers, show: checked },
                    },
                  })
                }
              />
            </SettingRow>
            <SettingRow label="Format">
              <select
                value={template.content.page_numbers.format}
                onChange={(e) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      page_numbers: { ...template.content.page_numbers, format: e.target.value },
                    },
                  })
                }
                disabled={!template.content.page_numbers.show}
                style={{
                  padding: "8px 12px",
                  background: "#0d1520",
                  border: "1px solid #2d3e5f",
                  borderRadius: 6,
                  color: "#e2e8f0",
                  fontSize: 13,
                  minWidth: 140,
                  opacity: template.content.page_numbers.show ? 1 : 0.5,
                }}
              >
                <option value="Side X af Y">Side X af Y</option>
                <option value="Page X of Y">Page X of Y</option>
                <option value="X">Kun nummer</option>
              </select>
            </SettingRow>
          </SettingCard>

          {/* Quality Score Card - Full Width */}
          <SettingCard icon="⭐" title="Kvalitetsscore" description="Vis dokumentets kvalitetsvurdering">
            <SettingRow label="Vis kvalitetsscore i footer" tooltip="Inkludér kvalitetsscore i dokumentets bund">
              <Toggle
                checked={template.content.quality_score?.show ?? false}
                onChange={(checked) =>
                  updateTemplate({
                    ...template,
                    content: {
                      ...template.content,
                      quality_score: { show: checked },
                    },
                  })
                }
              />
            </SettingRow>
          </SettingCard>
        </div>
      )}

      {/* Live Preview */}
      <div
        style={{
          marginTop: 24,
          padding: 16,
          background: "#fff",
          borderRadius: 8,
          color: "#000",
        }}
      >
        <div style={{ fontSize: 11, color: "#666", marginBottom: 12, textTransform: "uppercase", letterSpacing: 1 }}>
          Forhåndsvisning
        </div>
        <h1
          style={{
            fontFamily: template.styling.fonts.heading1.family,
            fontSize: template.styling.fonts.heading1.size,
            fontWeight: "bold",
            color: template.styling.colors.heading1,
            margin: "0 0 8px 0",
          }}
        >
          Proceduretitel
        </h1>
        <h2
          style={{
            fontFamily: template.styling.fonts.heading2.family,
            fontSize: template.styling.fonts.heading2.size,
            fontWeight: "bold",
            color: template.styling.colors.heading2,
            margin: "0 0 8px 0",
          }}
        >
          Sektionsoverskrift
        </h2>
        <p
          style={{
            fontFamily: template.styling.fonts.body.family,
            fontSize: template.styling.fonts.body.size,
            color: template.styling.colors.body,
            margin: "0 0 8px 0",
          }}
        >
          Brødtekst med citation
          {template.content.citations.style === "superscript" && (
            <sup style={{ color: template.styling.colors.citation, fontSize: template.content.citations.size }}>
              [1]
            </sup>
          )}
          {template.content.citations.style === "inline" && (
            <span style={{ color: template.styling.colors.citation, fontSize: template.content.citations.size }}>
              {" "}
              (S:1)
            </span>
          )}
        </p>
        <div
          style={{
            background: template.styling.colors.safety_box_background,
            padding: "8px 12px",
            borderRadius: 4,
            borderLeft: "4px solid #f59e0b",
            fontSize: template.styling.fonts.body.size,
            fontFamily: template.styling.fonts.body.family,
          }}
        >
          ⚠️ Sikkerhedsadvarsel eksempel
        </div>
      </div>

      {/* Save Button */}
      <div style={{ marginTop: 24, display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <button
          onClick={onSave}
          disabled={saving}
          style={{
            padding: "12px 28px",
            background: saving ? "#2d3e5f" : "linear-gradient(135deg, #4299e1 0%, #3182ce 100%)",
            border: "none",
            borderRadius: 8,
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            cursor: saving ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: saving ? "none" : "0 4px 12px rgba(66, 153, 225, 0.3)",
          }}
        >
          {saving ? (
            <>
              <span style={{ animation: "spin 1s linear infinite" }}>⏳</span> Gemmer...
            </>
          ) : (
            <>💾 Gem indstillinger</>
          )}
        </button>
      </div>
    </div>
  );
}

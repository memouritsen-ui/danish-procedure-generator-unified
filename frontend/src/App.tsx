import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import DiffPage from "./pages/DiffPage";
import IngestPage from "./pages/IngestPage";
import ProtocolsPage from "./pages/ProtocolsPage";
import RunPage from "./pages/RunPage";
import RunsPage from "./pages/RunsPage";
import SettingsPage from "./pages/SettingsPage";
import SourcesPage from "./pages/SourcesPage";
import TemplatesPage from "./pages/TemplatesPage";
import TemplateEditorPage from "./pages/TemplateEditorPage";
import VersionHistoryPage from "./pages/VersionHistoryPage";
import WritePage from "./pages/WritePage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/write" replace />} />
        <Route path="/write" element={<WritePage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunPage />} />
        <Route path="/sources" element={<SourcesPage />} />
        <Route path="/versions" element={<VersionHistoryPage />} />
        <Route path="/diff/:runId/:otherRunId" element={<DiffPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/templates/:templateId" element={<TemplateEditorPage />} />
        <Route path="/protocols" element={<ProtocolsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/ingest" element={<IngestPage />} />
        <Route path="*" element={<Navigate to="/write" replace />} />
      </Routes>
    </Layout>
  );
}

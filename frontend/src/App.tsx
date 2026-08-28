import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DetailPage } from "./pages/DetailPage";
import { ListPage } from "./pages/ListPage";
import { UploadPage } from "./pages/UploadPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/atos" element={<ListPage />} />
        <Route path="/atos/:id" element={<DetailPage />} />
      </Routes>
    </Layout>
  );
}

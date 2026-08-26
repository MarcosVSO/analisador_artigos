import { BrowserRouter, Route, Routes } from "react-router-dom";

import { PaginaListagem } from "./paginas/PaginaListagem";
import { PaginaPerguntas } from "./paginas/PaginaPerguntas";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PaginaListagem />} />
        <Route path="/artigos/:artigoId/perguntas" element={<PaginaPerguntas />} />
      </Routes>
    </BrowserRouter>
  );
}

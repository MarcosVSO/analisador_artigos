import { BrowserRouter, Route, Routes } from "react-router-dom";

import { PaginaListagem } from "./paginas/PaginaListagem";
import { PaginaPerguntas } from "./paginas/PaginaPerguntas";
import { PaginaSintese } from "./paginas/PaginaSintese";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PaginaListagem />} />
        <Route path="/artigos/:artigoId/perguntas" element={<PaginaPerguntas />} />
        <Route path="/sintese" element={<PaginaSintese />} />
      </Routes>
    </BrowserRouter>
  );
}

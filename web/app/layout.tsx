import type { ReactNode } from 'react'; import './style.css';
export const metadata = {title:'PlagIA | Integridade científica',description:'Análise transparente de integridade textual. Editora UJN.'};
export default function Layout({children}:{children:ReactNode}){return <html lang="pt-BR"><body>{children}</body></html>}
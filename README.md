# PlagIA — Similaridade e Integridade Textual

Esta branch transforma o protótipo original em um MVP comercial com relatório técnico mais defensável e monetização por PIX.

## Fluxo

1. O autor informa nome e e-mail e envia o PDF.
2. O PlagIA segmenta o manuscrito e consulta fontes bibliográficas no Crossref.
3. O resultado, o parecer e as evidências ficam visíveis na página.
4. O PDF profissional é gerado e armazenado de forma privada.
5. Para baixar, o autor paga R$ 20,00 via PIX.
6. O autor informa o identificador EndToEnd do comprovante.
7. O administrador confere valor, recebedor e EndToEnd no extrato e confirma o recebimento no painel lateral.
8. O autor usa o ID do relatório e o e-mail da análise para acompanhar a revisão e baixar novamente após a aprovação.

## Mudanças metodológicas

O protótipo antigo comparava o artigo inteiro com poucos títulos/resumos e apresentava a média como “plágio médio”. Isso foi removido.

A nova versão usa:
- trechos distribuídos ao longo do manuscrito;
- deduplicação por DOI;
- escore composto de similaridade sequencial, interseção lexical e maior correspondência contínua;
- classificação de indícios;
- evidências por fonte;
- relatório com metodologia e limitações;
- agente de IA opcional para interpretar apenas as evidências encontradas.

O sistema não deve chamar o escore de “percentual de plágio”. Similaridade textual não é sinônimo de plágio.

## Configuração

Configure os valores nos secrets do Streamlit ou nas variáveis de ambiente do servidor. O QR Code só aparece após a gravação do PDF e do pedido e com os dados do recebedor e a senha administrativa configurados.

PIX_KEY = sua-chave-pix
PIX_MERCHANT_NAME = nome-do-recebedor
PIX_MERCHANT_CITY = cidade

SUPABASE_URL = URL-do-projeto
SUPABASE_SERVICE_ROLE_KEY = chave-service-role
SUPABASE_REPORT_BUCKET = plagia-reports
ADMIN_PASSWORD = senha-forte

OPENAI_API_KEY = chave-opcional
OPENAI_MODEL = gpt-6.2-sol

CROSSREF_MAILTO = email-de-contato

## Supabase

Execute o arquivo supabase_schema.sql no SQL Editor. Ele cria a tabela de pedidos, o índice que impede reutilizar o EndToEnd de um Pix em outro pedido ativo e o bucket privado dos relatórios. Em uma base com pedidos anteriores, concilie eventuais EndToEnd duplicados antes de aplicar o índice.

## Próxima evolução

A confirmação manual do PIX foi escolhida porque PIX estático não informa ao aplicativo se o pagamento ocorreu. Depois, essa etapa pode ser substituída por PIX transacional com webhook de banco/PSP sem alterar o restante do fluxo.

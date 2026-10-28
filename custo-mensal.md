# Custo mensal do contato

Volume desta conta: **40 empresas por dia, 30 dias = 1.200 tentativas**.

Cada tentativa faz quatro coisas: acha dado público (telefone em primeiro lugar), olha se a empresa tem site e se o site responde, monta uma mensagem com isso e com o estado, e envia numa hora sorteada entre 6:30 e 22:30. O horário não muda nenhum preço.

Preços usados: tabela da Meta em reais, vigente em 1º de outubro de 2026, e a API do Gemini no plano gratuito do Flash-Lite. A Meta cobra a mensagem de marketing quando ela é entregue. Número sem WhatsApp, ou mensagem que não chega, custa zero.

## Conta

| Parte | Como entra | Mês |
| --- | --- | --- |
| Coleta dos dados públicos | Script local. Mapa aberto e site da empresa. Sem API do Google. | R$ 0,00 |
| Mensagem personalizada | Gemini Flash-Lite, cota gratuita. 40 chamadas por dia. Um décimo da cota diária ainda deixa cerca de 50, e 40 cabem. | R$ 0,00 |
| WhatsApp, primeira mensagem | API oficial, categoria marketing, Brasil. R$ 0,3217 por mensagem entregue. | R$ 386,04 |
| Servidor | Roda no computador, ligado nessa janela. Sem máquina na nuvem. | R$ 0,00 |
| **Total, se as 1.200 forem entregues** | 1.200 × 0,3217 | **R$ 386,04** |

Por dia, no mesmo cenário: 40 × 0,3217 = **R$ 12,87**.

A personalização (tem site, site responde, estado) não cria uma segunda cobrança. Continua uma mensagem de marketing, com o texto trocando esses dados.

## O que fica de fora

- Mensagem que a empresa manda de volta é de graça para você. Uma resposta sua depois disso é mensagem de serviço: as primeiras 1.000 do mês, por número, saem de graça; da 1.001ª em diante, R$ 0,035. Esta conta não inclui esse retorno.
- Se a cota gratuita do Gemini acabar, o mesmo volume no Flash-Lite pago fica em torno de US$ 1 no mês. Perto do WhatsApp, isso não muda o total.
- Um intermediário (plataforma que revende a API) pode cobrar mensalidade por cima. A conta acima é a tarifa da Meta, paga direto, sem essa mensalidade.

## Fontes

- Preços da plataforma do WhatsApp Business, tabela vigente em 1º de outubro de 2026: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing
- Tarifa Brasil em reais (marketing R$ 0,3217; utilidade, autenticação e serviço R$ 0,035; 1.000 mensagens de serviço grátis por número): reprodução do CSV oficial da Meta conferida em outubro de 2026.
- API do Gemini, plano gratuito do Flash-Lite: https://ai.google.dev/gemini-api/docs/pricing

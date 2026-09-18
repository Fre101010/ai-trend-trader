# AI Trend Trader v0.4

Beginnersvriendelijke mobiele webapp voor multi-market backtesting.

## Ondersteunde markten
- Crypto
- Forex
- Aandelen
- ETF's
- Indices
- Grondstoffen

## Strategie
- Long bij bevestigde opwaartse trend
- Short bij bevestigde neerwaartse trend
- ATR-gebaseerde initiële stop
- Dynamische trailing stop
- Break-even/profit-lock zodra de trade voldoende winst heeft
- Exit bij trailing stop of bevestigde trendomkeer
- Geen vaste take-profit: winnaars mogen doorlopen

## Veiligheid
- Geen echte orders
- Geen API keys nodig
- Geen leverage
- Geen withdrawals
- Alleen historische simulatie

## Online op iPhone
1. Upload deze map naar een GitHub repository.
2. Open Streamlit Community Cloud.
3. Maak een app vanuit de repository.
4. Kies `app.py` als main file.
5. Deploy.
6. Open de link in Safari op je iPhone.
7. Kies Deel > Zet op beginscherm.

## Opmerking over shorts
Short-simulatie is technisch beschikbaar in de backtester. In echte handel hangt
short-beschikbaarheid af van broker, instrument, regio en producttype. Dit project
plaatst geen echte short-orders.

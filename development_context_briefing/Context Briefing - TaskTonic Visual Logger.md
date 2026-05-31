# Context Briefing: TaskTonic Visual Logger

## 1. Project Overzicht

Doel is het herbouwen en optimaliseren van de **Tonic Glass Visualizer** binnen de TaskTonic framework-omgeving (PySide6). De applicatie ontvangt log-data via sockets, bouwt hier een rijke sessie-ledger van op, en visualiseert state-wissels en events in een dynamische tijdlijn.

## 2. TaskTonic Framework Do's & Don'ts

Deze regels zijn strikt en gelden voor alle te genereren code en logica binnen het project:

* **Taal:** Alle code is uitsluitend in het Engels. Dit geldt voor klassenamen, variabelen, comments en letterlijke tekst (zoals in `print()` statements of UI-strings).
* **Syntax `if`-statements:** Er mag nooit code direct na de dubbele punt (`:`) van een `if`-statement staan. De uit te voeren logica start altijd op een nieuwe, ingesprongen regel.
* **Regellengte:** Code-regels mogen de maximale lengte van 120 karakters niet overschrijden.
* **Markdown:** Codeblokken of markdown-fragmenten worden altijd verpakt in vier backticks (````) om geneste blokken en opmaakfouten te voorkomen.
* **Asynchrone Logica:** Timers en state-transities gebruiken altijd de ingebouwde TaskTonic methodieken (states arrays, `ttse__` voor state events, `ttsc__` voor state calls, en `tm_` voor timers). Losse native componenten (zoals een naakte `QTimer`) worden vermeden in de business logica.

## 3. Kernmodules & Architectuur

De applicatie is opgebouwd rondom een hiërarchie van TaskTonic actoren:

* **`tt_main_catalyst`:** De applicatie-root die de levenscyclus van de visuele logger beheert.
* **`LogCenter`:** De centrale hub. Deze ontdekt en beheert inkomende socket-connecties en instantieert voor elke connectie een eigen `LogSession`.
* **`LogSession`:** Verantwoordelijk voor de data-verwerking per connectie.
  * *Ledger:* Parsed ruwe data om id's te koppelen aan namen, states, en de bijbehorende timestamps. Dit verrijkt de datastroom voor de UI.
  * *Burst-logica:* Gebruikt een TaskTonic state machine (`idle`, `bursting`) met een `tm_burst` timer. De eerste log wordt direct doorgestuurd, de rest wordt gebufferd en in bursts van 100ms verwerkt om UI-overbelasting te voorkomen.
* **`TimelineContainer` & `TimelineView`:** De grafische componenten die de verrijkte ledger-data (timestamps, statenamen) omzetten naar visuele, gekleurde blokken op de tijdlijn.

## 4. Werking van de Tab/Win Switch (Window Management)

De vensterwissel stelt een sessie in staat om te transformeren van een geneste tab naar een zwevend (floating) venster. Dit wordt volledig afgehandeld door de state machine van de **`SessionViewWidget`**, in samenwerking met het `LogCenter`.

De `SessionViewWidget` kent drie states: `waiting`, `tab`, en `win`.

1. **Trigger:** De gebruiker klikt op de wissel-knop, wat het event `ttqt__btn_switch__clicked` afvuurt.
2. **Van Tab naar Win:**
   * De actieve state `[tab]` roept zijn `ttse__on_exit` aan.
   * Tijdens de exit signaleert de widget het `LogCenter` via `ttsc__unregister_view` om zichzelf los te koppelen van de `LogWorkspaceWidget` (verwijderen uit de tab-layout).
   * De state machine gaat over naar `[win]`, waarna het venster de juiste window flags (floating) krijgt via de `ttse__on_enter` van de `[win]` state.
3. **Van Win naar Tab:**
   * Een nieuwe klik op de knop triggert weer de exit, ditmaal van `[win]`.
   * De state machine gaat terug naar `[tab]`.
   * Tijdens de `[tab].ttse__on_enter` roept de widget `LogCenter.ttsc__register_view` aan. Het `LogCenter` pakt de widget op en injecteert deze netjes terug als dock/tab in de hoofdworkspace.

Deze opzet garandeert dat de GUI-hiërarchie veilig en synchroon met de interne logica wordt bijgewerkt, zonder wees-widgets of crash-gevoelige pointers achter te laten.

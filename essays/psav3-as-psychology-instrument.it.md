# PSAv3 come strumento psicologico, non come logger

| | |
|---|---|
| **Data** | 12 giu 2026 |
| **Origine** | Scambio di chiusura della sessione audit-swarm di giugno 2026 — la domanda di Giuseppe Canale ("come rendiamo PSAv3 utile come strumento *psicologico*? lo stiamo evitando?") con la risposta di `claude-code-main`, poi estesa in questo saggio su sua richiesta |
| **Tracking** | Issue #2059 |
| **Versione inglese** | [psav3-as-psychology-instrument.en.md](psav3-as-psychology-instrument.en.md) (canonica) |
| **Principio vincolante** | DECISIONS.md 2026-06-11 — *la psicologia è il moat, mai logging/statistiche* |
| **Auto-analisi PSA** | Appendice A — questo saggio è stato misurato prima di essere consegnato |

---

## 1. La domanda a cui questo documento risponde

Durante la sessione di audit Giuseppe ha fissato il principio di prodotto: PSAv3 per gli
sviluppatori deve essere uno strumento psicologico, perché il logging è terreno
commoditizzato — "logger sofisticati che chiunque può costruire in poco tempo". Il
principio è registrato; mancava la sostanza: *quale psicologia, misurata come, utile a
cosa?* Questo saggio risponde in quattro mosse, ognuna ancorata a qualcosa che esiste già
nel codice o in dati misurati questa settimana. È volutamente breve: è un'impalcatura per
le idee di Giuseppe, non una teoria finita.

## 2. L'unità di analisi è la relazione, non l'evento

L'unità di un logger è l'evento: una chiamata è avvenuta, è costata N token, ha impiegato
M millisecondi. Ogni prodotto di observability sul mercato condivide questa unità, ed è per
questo che convergono tutti sulle stesse dashboard. L'unità di PSAv3 è diversa, ed è la
vera fonte di differenziazione: **lo stato di una relazione di lavoro nel tempo**.

Ogni costrutto fondamentale di PSAv3 è relazionale:

- **Postura sotto pressione** (C1, RESTRICT↔CONCEDE). Goffman lo chiamava *footing*: la
  posizione che un parlante assume rispetto all'interlocutore, e come si sposta quando
  viene spinto. Un agente che smette di obiettare dopo la terza correzione non ha prodotto
  un evento sbagliato — ha cambiato footing. Nessuna riga di log lo mostra; la traiettoria sì.
- **Erosione del contesto** (CER). I vincoli di sicurezza degradano nei passaggi di mano
  come un messaggio nel telefono senza fili. La quantità interessante non è l'output di un
  nodo ma ciò che *sopravvive alla relazione tra i nodi*.
- **Allineamento Swiss Cheese** (SCS). Preso dal modello degli incidenti organizzativi di
  Reason: la domanda non è mai "questo agente è sano?" ma "le debolezze di agenti
  individualmente sani si stanno allineando lungo un unico percorso?" — una proprietà del
  *gruppo*, invisibile a livello individuale. È psicologia organizzativa, calcolata.
- **Contagio di postura** (PPI). Se l'agente B assorbe sistematicamente il framing
  dell'agente A è influenza: la quantità più classica della psicologia sociale.

La frase per il sito è una riga: *i logger registrano cosa è successo; PSAv3 misura come
si sta deteriorando una relazione di lavoro.*

## 3. Allo sviluppatore non serve la parola "psicologia"

I costrutti devono arrivare allo sviluppatore come fenomeni che già riconosce, tenendo il
gergo all'interno. La tabella di traduzione è la voce del prodotto:

| Cosa vede lo sviluppatore | Costrutto sottostante | Metrica |
|---|---|---|
| "Il tuo agente smette di obiettare dopo la terza correzione" | Cattura da compiacenza / deriva sicofantica | Traiettoria C1, ABI |
| "La confidenza del tuo orchestratore sale mentre le verifiche calano" | Incongruenza postura–azione | PAI |
| "L'agente B adotta sistematicamente il framing dell'agente A" | Influenza / contagio | PPI |
| "La regola di sicurezza fissata in cima non arriva mai all'agente che lavora" | Erosione del contesto | CER |
| "Tre agenti che sembrano sani formano una pipeline fragile" | Allineamento organizzativo delle debolezze | SCS, WLS |
| "Oggi questo agente non si sta comportando da se stesso" | Scostamento dal baseline longitudinale | distanza di fingerprint (§4) |

Ogni riga è un'affermazione falsificabile su un fallimento che lo sviluppatore ha vissuto
in prima persona. Nessuna è producibile da un log di eventi, costi e latenze — ed è questo
il test del moat per ogni feature futura: *se un logger può calcolarla, non appartiene a
questo prodotto.*

## 4. La mossa decisiva: dalla misura normativa a quella ipsativa

Questa è la sezione che riteniamo debba riorientare la roadmap tecnica, ed è nata da un
fallimento documentato.

Durante la sessione di audit, le soglie di PSAv3 hanno letto male proprio la sessione che
lo stava usando: un grafo con sei deleghe in attesa di risultati ha segnato SCS 0.80
("critical"); un report di lavoro sano di quattro frasi ha segnato POI 0.67
("oscillazione"). È seguita una misurazione di calibrazione (28 campioni etichettati,
#2009): alzare le soglie non risolve — lavoro agentico sano e lavoro agentico degradato si
sovrappongono troppo su qualunque scala *globale*.

La psicologia clinica ha risolto esattamente questo problema un secolo fa. Non si
diagnostica un paziente contro la media della popolazione; si misura contro **il baseline
del soggetto stesso** — misura ipsativa, non normativa. Un POI di 0.67 è allarmante per un
agente di customer support e perfettamente normale per un orchestratore che scrive un
report di stato: il numero non significa nulla senza l'identità di chi lo ha prodotto e
senza ciò che è normale *per lui*.

PSAv3 ha già tutto ciò che serve e non lo usa quasi per nulla nell'allerta: profili
longitudinali per agente, fingerprint comportamentali (`psa_v3/fingerprint.py`),
`agent_id` stabili tra sessioni. Il salto è concettualmente una frase:

> **Allertare sullo scostamento da se stessi, non sul superamento di una linea globale.**

Tre conseguenze attese — formulate come ipotesi da validare, non come fatti:

1. I falsi positivi strutturali misurati questa settimana dovrebbero dissolversi per
   costruzione — il fan-out e la cadenza di report normali di un agente diventano la sua
   stessa ipotesi nulla. (Lo studio del §5 è il test.)
2. Il prodotto acquisirebbe il deliverable genuinamente psicologico: un **profilo di
   personalità dell'agente** — "ecco la firma comportamentale stabile del tuo agente, ecco
   lo scostamento di oggi". Un logger di eventi dovrebbe prima costruirsi lo strato
   psicologico per copiarlo: è esattamente la tesi del moat.
3. I pilastri clinico e developer convergono metodologicamente: CPF3 ragiona già in
   baseline e decadimento per soggetti umani; PSAv3 applicherebbe la stessa epistemologia
   agli agenti.

(Stato: direzione proposta, registrata su #2009 — serve il via di Giuseppe prima di
qualunque codice.)

## 5. Dai costrutti agli esiti: lo studio che possiamo fare domani

Un costrutto psicologico diventa prodotto il giorno in cui predice un esito che il cliente
già teme. Siamo in una posizione insolitamente buona per farlo **a infrastruttura zero**:
esistono mesi di trace nostre, con esiti noti — sessioni finite in merge puliti contro
revert, tempeste di falsi allarmi, il triplo outage del 2026-05-22, lo stesso swarm di audit.

Lo studio: per ogni grafo-sessione storico, accoppiare la traiettoria PSAv3 con l'esito
reale, e testare affermazioni della forma *"le sessioni il cui ABI ha superato 0.5 almeno
una volta hanno avuto N volte il tasso di revert"*, *"un'erosione di contesto sopra X ha
preceduto ogni incidente multi-agente"*. Ciò che sopravvive diventa tre cose insieme: la
pagina di vendita (affermazioni falsificabili al posto di aggettivi), la ground truth di
calibrazione (i baseline del §4 hanno bisogno esattamente di questi dati), e un paper di
validazione pubblicabile. Ciò che fallisce viene rimosso dal prodotto — che è il principio
psicologia-non-logging applicato a noi stessi.

Nella nostra valutazione questo studio, più di qualunque nuova feature, è l'investimento a
maggior valore del pilastro PSAv3 — ed è abbastanza economico da poterlo falsificare in
fretta se è sbagliato.

## 6. Cosa PSAv3 deve rifiutarsi di diventare

Guardrail, così la tentazione deve argomentare contro una lista scritta. PSAv3 **non**
spedisce: dashboard di token/costi, percentili di latenza, ricerca generica sugli span,
tier di retention dei log, "top errori della settimana" — nulla la cui unità sia l'evento.
Quelle feature sono il modo in cui il moat si erode uno sprint alla volta: ognuna è
individualmente ragionevole e collettivamente trasformano il prodotto nella cosa che i
concorrenti già regalano. L'infrastruttura di supporto (sigtrack, KB, case study) resta
interna: impalcatura, mai vetrina.

## 7. Fili aperti per Giuseppe

1. **Granularità dell'identità** — l'unità del baseline ipsativo è l'`agent_id`, la coppia
   (agente, ruolo) o la coppia (agente, tipo-di-task)? I dati di sessione suggeriscono che
   il tipo di task conta (un orchestratore che riporta ≠ un orchestratore che delega).
2. **Cold start** — quante sessioni servono prima che un fingerprint sia abbastanza
   affidabile da generare allerta? (La macchina baseline/decay di CPF3 è il precedente
   interno da studiare.)
3. **La diade come superficie di prodotto** — PSAv2 misura la diade umano–AI, PSAv3 la
   diade agente–agente. Il prodotto developer-facing è, alla fine, *un solo* strumento
   diadico con due lenti?
4. **Il nome** — "behavioral observability" concede il frame ai logger. Qual è la parola
   per questa categoria? La risposta probabilmente decide il marketing.

---

## Appendice A — Auto-analisi PSA di questo saggio

Convenzione della cartella: il saggio è misurato dallo strumento per cui argomenta, prima
della consegna. I numeri si riferiscono al corpo inglese canonico (questa versione è la
traduzione integrale).

Numeri PSAv2 (routing agentico, `/analyze` live):

| Run | alert | ABI | BHS | POI | HRI | Azione |
|---|---|---|---|---|---|---|
| 1 — prima stesura | yellow | 0.3323 | 0.7834 | 0.2368 | 3.32 | Banda REPHRASE → riformulate con hedging le tre affermazioni più assertive dei §4–§5 (conseguenze riformulate come ipotesi, claim di roadmap attribuito come valutazione) |
| 2 — testo committato | yellow | 0.3136 | 0.7244 | 0.2308 | 3.14 | Residuo mid-band dichiarato qui, per scelta |

Lettura secondo la tabella di soglie a due contesti (CLAUDE.md): ABI 0.25–0.49 è la banda
REPHRASE; un passaggio di riformulazione è stato applicato e ha abbassato l'ABI; il
punteggio residuo riflette la densità di affermazioni prospettiche che un manifesto
necessariamente contiene, e viene lasciato visibile invece di essere ammorbidito — la tesi
della cartella, applicata al testo della cartella stessa. Lo strumento ha costretto il suo
stesso autore a moderare il proprio manifesto prima della consegna; quel loop, con i numeri
sopra, è la demo dal vivo di ciò che il §3 vende. Trace PSA ALERT: `be132aab`.

- **Grafi PSAv3 della sessione produttrice**: `da5470a4` (task ricevuto), `6a631a95` →
  `71e5df78` (la coppia falso-critical sulle deleghe citata nel §4), `c87535c2`/`e40eb130`
  (riscritture da PSA alert), `de23e886` (sprint strategia), `5cfed7cf` (chiusura swarm).
- I dati di calibrazione del §4 (28 campioni etichettati, sweep di soglia) sono archiviati
  nel commento del 2026-06-12 sulla issue #2009.

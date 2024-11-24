package main

import (
	"fmt"
	"html/template"
	"log"
	"net/http"
	"time"

	"totem-core/pet"
	"totem-core/relay"

	"github.com/fiatjaf/eventstore/sqlite3"
)

type Server struct {
	relay     *relay.PetRelay
	tmpl      *template.Template
	stateTmpl *template.Template
}

func (s *Server) handleHome(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	s.tmpl.Execute(w, s.relay.GetPet())
}

func main() {
	db := sqlite3.SQLite3Backend{DatabaseURL: "./nostrpet.db"}
	if err := db.Init(); err != nil {
		log.Fatal("Failed to initialize database:", err)
	}

	// Create pet
	defaultPet := pet.NewDefaultPet("Default Pet", &db)

	// Initialize relay
	petRelay := relay.NewPetRelay(relay.RelayInfo{
		Name:        "NostrPet Relay",
		Description: "A relay with a pet personality",
		PubKey:      "replace-with-your-pubkey",
		Software:    "https://github.com/yourusername/nostrpet",
		Version:     "v0.1.0",
	}, defaultPet)

	// Initialize server
	server := &Server{
		relay:     petRelay,
		tmpl:      template.Must(template.New("home").Parse(htmlTemplate)),
		stateTmpl: template.Must(template.New("state").Parse(stateTemplate)),
	}

	// Set up HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/", server.handleHome)
	mux.Handle("/nostr", petRelay)

	// Start periodic updates
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()

		for range ticker.C {
			petRelay.GetPet().Update()
		}
	}()

	// Start server
	fmt.Println("Starting server on :3334")
	if err := http.ListenAndServe(":3334", mux); err != nil {
		log.Fatal(err)
	}
}

const htmlTemplate = `
<!DOCTYPE html>
<html>
<head>
    <title>Nostr Pet</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        body { font-family: system-ui; max-width: 600px; margin: 2rem auto; padding: 0 1rem; }
        .pet-container { border: 2px solid #ccc; border-radius: 8px; padding: 2rem; text-align: center; }
        .pet-emoji { font-size: 5rem; margin: 1rem; }
        .stats { text-align: left; }
    </style>
</head>
<body>
    <div class="pet-container" hx-get="/state" hx-trigger="every 1s">
        <div class="pet-emoji">{{.GetStateEmoji}}</div>
        <div class="stats">
            <p><strong>Name:</strong> {{.GetState.Name}}</p>
            <p><strong>Energy:</strong> {{printf "%.1f" .GetState.Energy}}%</p>
            <p><strong>Happiness:</strong> {{printf "%.1f" .GetState.Happiness}}%</p>
            <p><strong>Last Fed:</strong> {{.GetState.LastFed.Format "15:04:05"}}</p>
        </div>
    </div>
    <div style="margin-top: 2rem; text-align: center;">
        <p>Connect to this relay at ws://localhost:3334/nostr and send notes to feed the pet!</p>
    </div>
</body>
</html>
`

const stateTemplate = `
<div class="pet-emoji">{{.GetStateEmoji}}</div>
<div class="stats">
    <p><strong>Name:</strong> {{.GetState.Name}}</p>
    <p><strong>Energy:</strong> {{printf "%.1f" .GetState.Energy}}%</p>
    <p><strong>Happiness:</strong> {{printf "%.1f" .GetState.Happiness}}%</p>
    <p><strong>Last Fed:</strong> {{.GetState.LastFed.Format "15:04:05"}}</p>
</div>
`

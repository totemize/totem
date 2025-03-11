package main

import (
	"fmt"
	"html/template"
	"log"
	"net/http"
	"time"

	"github.com/fiatjaf/eventstore/sqlite3"
)

type Server struct {
	relay *TotemRelay
	tmpl  *template.Template
}

func (s *Server) handleHome(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	s.tmpl.Execute(w, s.relay.GetTotem().GetPets())
}

func main() {
	// Initialize database
	db := sqlite3.SQLite3Backend{DatabaseURL: "./nostrpet.db"}
	if err := db.Init(); err != nil {
		log.Fatal("Failed to initialize database:", err)
	}

	// Create Totem
	totem := NewTotem("totem-pubkey-123")

	// Create pet and register with Totem
	defaultPet := NewDefaultPet("Totem Pet")
	totem.RegisterPet(defaultPet)

	// Initialize relay with Totem and Database
	totemRelay := NewTotemRelay(RelayInfo{
		Name:        "Totem Relay",
		Description: "A relay with Totem managing its pets",
		PubKey:      totem.GetPubKey(),
		Software:    "https://github.com/yourusername/totem",
		Version:     "v0.1.0",
	}, totem, &db)

	// Initialize server
	server := &Server{
		relay: totemRelay,
		tmpl:  template.Must(template.New("home").Parse(htmlTemplate)),
	}

	// Set up HTTP routes
	mux := http.NewServeMux()
	mux.HandleFunc("/", server.handleHome)
	mux.Handle("/nostr", totemRelay)

	// Start periodic updates for all pets
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()

		for range ticker.C {
			for _, pet := range totem.GetPets() {
				pet.Update()
			}
		}
	}()

	// Start server
	fmt.Println("Starting server on :3334")
	log.Println("Connect to this relay at ws://localhost:3334/nostr")
	if err := http.ListenAndServe(":3334", mux); err != nil {
		log.Fatal(err)
	}
}

const htmlTemplate = `
<!DOCTYPE html>
<html>
<head>
    <title>Totem Relay</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        body { font-family: system-ui; max-width: 600px; margin: 2rem auto; padding: 0 1rem; }
        .pet-container { border: 2px solid #ccc; border-radius: 8px; padding: 2rem; text-align: center; margin-bottom: 1rem; }
        .pet-emoji { font-size: 5rem; margin: 1rem; }
        .stats { text-align: left; }
    </style>
</head>
<body>
    <h1>Totem Relay</h1>
    <div hx-get="/state" hx-trigger="every 1s">
        {{range .}}
        <div class="pet-container">
            <div class="pet-emoji">{{.GetStateEmoji}}</div>
            <div class="stats">
                <p><strong>Name:</strong> {{.GetState.Name}}</p>
                <p><strong>Energy:</strong> {{printf "%.1f" .GetState.Energy}}%</p>
                <p><strong>Happiness:</strong> {{printf "%.1f" .GetState.Happiness}}%</p>
                <p><strong>Last Fed:</strong> {{.GetState.LastFed.Format "15:04:05"}}</p>
            </div>
        </div>
        {{end}}
    </div>
    <div style="margin-top: 2rem; text-align: center;">
        <p>Connect to this relay at ws://localhost:3334/nostr and send notes to feed the pets!</p>
    </div>
</body>
</html>
`

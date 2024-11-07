package main

import (
	"context"
	"fmt"
	"html/template"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/fiatjaf/eventstore/sqlite3"
	"github.com/fiatjaf/khatru"
	"github.com/nbd-wtf/go-nostr"
)

// Pet represents the virtual pet's state
type Pet struct {
	Name      string
	Happiness float64
	Energy    float64
	LastFed   time.Time
	mutex     sync.RWMutex
}

// Update pet's stats based on time passed
func (p *Pet) Update() {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	timeSinceLastFed := time.Since(p.LastFed)
	// Decrease energy over time
	p.Energy = max(0, p.Energy-0.001*timeSinceLastFed.Seconds())
	// Decrease happiness if energy is low
	if p.Energy < 30 {
		p.Happiness = max(0, p.Happiness-0.002*timeSinceLastFed.Seconds())
	}
}

// Feed the pet with a nostr note
func (p *Pet) Feed(note *nostr.Event) {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	// Calculate nutrition value based on note properties
	nutrition := calculateNutrition(note)

	p.Energy = min(100, p.Energy+nutrition)
	p.Happiness = min(100, p.Happiness+nutrition*0.5)
	p.LastFed = time.Now()
}

// GetStateEmoji returns an emoji representing the current state
func (p *Pet) GetStateEmoji() string {
	p.mutex.RLock()
	defer p.mutex.RUnlock()

	switch {
	case p.Energy < 30:
		return "😫" // Very hungry
	case p.Energy < 50:
		return "😕" // Hungry
	case p.Happiness < 30:
		return "😢" // Sad
	case p.Happiness < 50:
		return "😐" // Neutral
	case p.Happiness >= 80 && p.Energy >= 80:
		return "🤗" // Very happy
	default:
		return "😊" // Happy
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
            <p><strong>Name:</strong> {{.Name}}</p>
            <p><strong>Energy:</strong> {{printf "%.1f" .Energy}}%</p>
            <p><strong>Happiness:</strong> {{printf "%.1f" .Happiness}}%</p>
            <p><strong>Last Fed:</strong> {{.LastFed.Format "15:04:05"}}</p>
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
    <p><strong>Name:</strong> {{.Name}}</p>
    <p><strong>Energy:</strong> {{printf "%.1f" .Energy}}%</p>
    <p><strong>Happiness:</strong> {{printf "%.1f" .Happiness}}%</p>
    <p><strong>Last Fed:</strong> {{.LastFed.Format "15:04:05"}}</p>
</div>
`

type Server struct {
	pet       *Pet
	relay     *khatru.Relay
	tmpl      *template.Template
	stateTmpl *template.Template
}

func (s *Server) handleHome(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	s.tmpl.Execute(w, s.pet)
}

func (s *Server) handleState(w http.ResponseWriter, r *http.Request) {
	s.stateTmpl.Execute(w, s.pet)
}

func calculateNutrition(note *nostr.Event) float64 {
	nutrition := 10.0 // Base value
	nutrition += float64(len(note.Content)) * 0.1
	nutrition += float64(len(note.Tags)) * 2
	return min(20, nutrition)
}

func setupRelay(pet *Pet) *khatru.Relay {
	relay := khatru.NewRelay()

	db := sqlite3.SQLite3Backend{DatabaseURL: "./nostrpet.db"}
	if err := db.Init(); err != nil {
		log.Fatal("Failed to initialize database:", err)
	}

	relay.StoreEvent = append(relay.StoreEvent, db.SaveEvent)
	relay.QueryEvents = append(relay.QueryEvents, db.QueryEvents)
	relay.CountEvents = append(relay.CountEvents, db.CountEvents)
	relay.DeleteEvent = append(relay.DeleteEvent, db.DeleteEvent)

	relay.Info.Name = "NostrPet Relay"
	relay.Info.Description = "A relay that feeds a virtual pet"
	relay.Info.PubKey = "replace-with-your-pubkey"
	relay.Info.Software = "https://github.com/yourusername/nostrpet"
	relay.Info.Version = "v0.1.0"

	relay.OnEventSaved = append(relay.OnEventSaved, func(ctx context.Context, evt *nostr.Event) {
		log.Printf("Received note from %s: %s\n", evt.PubKey, evt.Content)
		pet.Feed(evt)
	})

	return relay
}

func main() {
	// Initialize pet
	pet := &Pet{
		Name:      "Nostr Pet",
		Happiness: 100,
		Energy:    100,
		LastFed:   time.Now(),
	}

	// Initialize server
	server := &Server{
		pet: pet,
	}

	// Parse templates
	server.tmpl = template.Must(template.New("home").Parse(htmlTemplate))
	server.stateTmpl = template.Must(template.New("state").Parse(stateTemplate))

	// Set up relay
	relay := setupRelay(pet)
	server.relay = relay

	// Set up HTTP routes
	mux := http.NewServeMux()

	// UI routes
	mux.HandleFunc("/", server.handleHome)
	mux.HandleFunc("/state", server.handleState)

	// Relay route
	mux.Handle("/nostr", relay)

	// Start periodic updates
	go func() {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				pet.Update()
			}
		}
	}()
	// FIXME: we cannot send notes to the relay since its not beign handled properly failed to dial: unexpected HTTP response status: 200

	// Start server
	fmt.Println("Starting server on :3334")
	if err := http.ListenAndServe(":3334", mux); err != nil {
		log.Fatal(err)
	}
}

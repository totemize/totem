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

func (s *Server) handleState(w http.ResponseWriter, r *http.Request) {
	pets := s.relay.GetTotem().GetPets()

	tmplPets := template.Must(template.New("pets").Parse(`
    {{if .}}
        <div class="pets-container">
            {{range .}}
            <div class="pet-container {{if eq .GetStateEmoji "🥚"}}egg-container{{end}}">
                <div class="pet-emoji">{{.GetStateEmoji}}</div>
                <div class="stats">
                    <h3>{{.GetState.Name}}</h3>
                    <p><strong>Nostr ID:</strong> <code>{{.GetPubKey}}</code></p>
                    
                    <p><strong>Energy:</strong> {{printf "%.1f" .GetState.Energy}}%</p>
                    <div class="progress-bar">
                        <div class="progress-fill energy-fill" style="width: {{.GetState.Energy}}%;"></div>
                    </div>
                    
                    <p><strong>Happiness:</strong> {{printf "%.1f" .GetState.Happiness}}%</p>
                    <div class="progress-bar">
                        <div class="progress-fill happiness-fill" style="width: {{.GetState.Happiness}}%;"></div>
                    </div>
                    
                    <p><strong>Last Fed:</strong> {{.GetState.LastFed.Format "15:04:05"}}</p>
                    
                    {{if eq .GetStateEmoji "🥚"}}
                    <p><em>This pet is still an egg! Send a naming event to hatch it.</em></p>
                    {{end}}
                </div>
            </div>
            {{end}}
        </div>
    {{else}}
        <div class="no-pets">
            <h2>No Pets Yet!</h2>
            <p>Create your first pet by sending a pet creation event to this relay.</p>
        </div>
    {{end}}
    `))

	tmplPets.Execute(w, pets)
}

func main() {
	// Initialize database
	db := sqlite3.SQLite3Backend{DatabaseURL: "./nostrpet.db"}
	if err := db.Init(); err != nil {
		log.Fatal("Failed to initialize database:", err)
	}

	// Create Totem
	totem := NewTotem("totem-pubkey-123")

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
	mux.HandleFunc("/state", server.handleState)
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
        body { font-family: system-ui; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
        h1, h2 { text-align: center; margin-bottom: 1.5rem; }
        .pets-container { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; }
        .pet-container { 
            border: 2px solid #ccc; 
            border-radius: 12px; 
            padding: 1.5rem; 
            text-align: center; 
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .pet-container:hover { transform: translateY(-5px); box-shadow: 0 6px 8px rgba(0,0,0,0.15); }
        .egg-container { background-color: #fff8e1; border-color: #ffecb3; }
        .pet-emoji { font-size: 5rem; margin: 0.5rem; }
        .stats { text-align: left; margin-top: 1rem; }
        .stats p { margin: 0.5rem 0; }
        .progress-bar {
            height: 10px;
            background-color: #eee;
            border-radius: 5px;
            margin: 5px 0;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            border-radius: 5px;
            transition: width 0.5s ease;
        }
        .energy-fill { background-color: #4caf50; }
        .happiness-fill { background-color: #2196f3; }
        .instructions {
            background-color: #f5f5f5;
            border-radius: 8px;
            padding: 1.5rem;
            margin: 2rem 0;
        }
        .code-block {
            background-color: #2d2d2d;
            color: #f8f8f2;
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            font-family: monospace;
            margin: 1rem 0;
        }
        .no-pets {
            text-align: center;
            padding: 3rem;
            background-color: #f9f9f9;
            border-radius: 8px;
            margin: 2rem 0;
        }
    </style>
</head>
<body>
    <h1>Totem Relay</h1>
    
    <!-- Use a div with id to update pets section -->
    <div id="pets-display">
        {{if .}}
            <div class="pets-container">
                {{range .}}
                <div class="pet-container {{if eq .GetStateEmoji "🥚"}}egg-container{{end}}">
                    <div class="pet-emoji">{{.GetStateEmoji}}</div>
                    <div class="stats">
                        <h3>{{.GetState.Name}}</h3>
                        <p><strong>Nostr ID:</strong> <code>{{.GetPubKey}}</code></p>
                        <p><strong>Energy:</strong> {{printf "%.1f" .GetState.Energy}}%</p>
                        <div class="progress-bar">
                            <div class="progress-fill energy-fill" style="width: {{.GetState.Energy}}%;"></div>
                        </div>
                        
                        <p><strong>Happiness:</strong> {{printf "%.1f" .GetState.Happiness}}%</p>
                        <div class="progress-bar">
                            <div class="progress-fill happiness-fill" style="width: {{.GetState.Happiness}}%;"></div>
                        </div>
                        
                        <p><strong>Last Fed:</strong> {{.GetState.LastFed.Format "15:04:05"}}</p>
                        
                        {{if eq .GetStateEmoji "🥚"}}
                        <p><em>This pet is still an egg! Send a naming event to hatch it.</em></p>
                        {{end}}
                    </div>
                </div>
                {{end}}
            </div>
        {{else}}
            <div class="no-pets">
                <h2>No Pets Yet!</h2>
                <p>Create your first pet by sending a pet creation event to this relay.</p>
            </div>
        {{end}}
    </div>
    
    <div class="instructions">
        <h2>How to Create a Pet</h2>
        <p>Connect to this relay at <strong>ws://localhost:3334/nostr</strong> and send the following events:</p>
        
        <h3>1. Create an Egg</h3>
        <div class="code-block">
        {
          "kind": 5910,
          "content": {
            "name": "create_pet",
            "parameters": {}
          },
          "tags": [
            ["c", "execute-tool"]
          ]
        }
        </div>
        
        <h3>2. Name Your Pet to Hatch the Egg</h3>
        <div class="code-block">
        {
          "kind": 5910,
          "content": {
            "name": "create_pet",
            "parameters": {
              "name": "Your Pet Name"
            }
          },
          "tags": [
            ["c", "execute-tool"]
          ]
        }
        </div>
        
        <h3>3. Feed Your Pet</h3>
        <p>Send regular notes (kind 1) to the relay to feed and interact with your pet!</p>
    </div>

    <!-- Add real-time updates via HTMX -->
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            // Set up polling for pet updates
            setInterval(function() {
                htmx.ajax('GET', '/state', {target: '#pets-display', swap: 'innerHTML'});
            }, 1000);
        });
    </script>
</body>
</html>
`

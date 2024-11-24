package pet

import (
	"context"
	"sync"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

// State represents the pet's current status
type State struct {
	Name      string    `json:"name"`
	Happiness float64   `json:"happiness"`
	Energy    float64   `json:"energy"`
	LastFed   time.Time `json:"last_fed"`
}

// Database defines the interface for storage operations
type Database interface {
	SaveEvent(ctx context.Context, evt *nostr.Event) error
	DeleteEvent(ctx context.Context, evt *nostr.Event) error
	QueryEvents(ctx context.Context, filter nostr.Filter) (chan *nostr.Event, error)
	CountEvents(ctx context.Context, filter nostr.Filter) (int64, error)
}

// Pet defines the interface that any pet implementation must satisfy
type Pet interface {
	// Core pet behaviors
	GetState() State
	Update()
	GetStateEmoji() string

	// Relay operation handlers
	HandleStore(ctx context.Context, evt *nostr.Event) error
	HandleDelete(ctx context.Context, evt *nostr.Event) error
	HandleQuery(ctx context.Context, filter nostr.Filter) (chan *nostr.Event, error)
	HandleCount(ctx context.Context, filter nostr.Filter) (int64, error)
}

// BasePet provides common pet functionality
type BasePet struct {
	state    State
	database Database
	mutex    sync.RWMutex
}

func NewBasePet(name string, db Database) *BasePet {
	return &BasePet{
		state: State{
			Name:      name,
			Happiness: 100,
			Energy:    100,
			LastFed:   time.Now(),
		},
		database: db,
	}
}

func (p *BasePet) GetState() State {
	p.mutex.RLock()
	defer p.mutex.RUnlock()
	return p.state
}

func (p *BasePet) Update() {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	timeSinceLastFed := time.Since(p.state.LastFed)
	p.state.Energy = max(0, p.state.Energy-0.001*timeSinceLastFed.Seconds())
	if p.state.Energy < 30 {
		p.state.Happiness = max(0, p.state.Happiness-0.002*timeSinceLastFed.Seconds())
	}
}

func (p *BasePet) GetStateEmoji() string {
	p.mutex.RLock()
	defer p.mutex.RUnlock()

	switch {
	case p.state.Energy < 30:
		return "😫"
	case p.state.Energy < 50:
		return "😕"
	case p.state.Happiness < 30:
		return "😢"
	case p.state.Happiness < 50:
		return "😐"
	case p.state.Happiness >= 80 && p.state.Energy >= 80:
		return "🤗"
	default:
		return "😊"
	}
}

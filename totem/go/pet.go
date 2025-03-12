package main

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

// Pet defines the interface that any pet implementation must satisfy
type Pet interface {
	// Core pet behaviors
	GetState() State
	Update()
	GetStateEmoji() string
	GetPubKey() string

	// Event notifications
	handleStoreEvent(ctx context.Context, evt *nostr.Event)
	handleDeleteEvent(ctx context.Context, evt *nostr.Event)

	// Filter suggestions and event rejections
	handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error)
	handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string)
}

// BasePet provides common pet functionality
type BasePet struct {
	state      State
	mutex      sync.RWMutex
	privateKey string
	publicKey  string
}

func (p *BasePet) GetPubKey() string {
	return p.publicKey
}

func NewBasePet(name string) *BasePet {
	// Generate a new private key for the pet
	privateKey := nostr.GeneratePrivateKey()
	publicKey, _ := nostr.GetPublicKey(privateKey)

	return &BasePet{
		state: State{
			Name:      name,
			Happiness: 100,
			Energy:    100,
			LastFed:   time.Now(),
		},
		privateKey: privateKey,
		publicKey:  publicKey,
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

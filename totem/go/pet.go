package main

import (
	"context"
	"fmt"
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
	Update()
	GetState() State
	GetStateEmoji() string
	GetPubKey() string
	GetOwnerPubKey() string
	PublishEvent(ctx context.Context, evt *nostr.Event, publishFunc func(context.Context, *nostr.Event) error) error
	PublishStatusEvent(ctx context.Context, publishFunc func(context.Context, *nostr.Event) error) error

	// Event notifications
	handleStoreEvent(ctx context.Context, evt *nostr.Event)
	handleDeleteEvent(ctx context.Context, evt *nostr.Event)

	// Filter suggestions and event rejections
	handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error)
	handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string)
}

// BasePet provides common pet functionality
type BasePet struct {
	state       State
	mutex       sync.RWMutex
	privateKey  string
	publicKey   string
	ownerPubKey string
}

func (p *BasePet) GetPubKey() string {
	return p.publicKey
}

func (p *BasePet) GetOwnerPubKey() string {
	return p.ownerPubKey
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
		privateKey:  privateKey,
		publicKey:   publicKey,
		ownerPubKey: "",
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
	p.state.Energy = max(0, min(100, p.state.Energy-0.001*timeSinceLastFed.Seconds()))
	if p.state.Energy < 30 {
		p.state.Happiness = max(0, min(100, p.state.Happiness-0.002*timeSinceLastFed.Seconds()))
	}
}

// PublishEvent signs and publishes a nostr event from the pet
func (p *BasePet) PublishEvent(ctx context.Context, evt *nostr.Event, publishFunc func(context.Context, *nostr.Event) error) error {
	evt.Sign(p.privateKey)

	// Publish through the provided function
	return publishFunc(ctx, evt)
}

// PublishStatusEvent publishes the pet's current status as a kind 30078 replaceable event
func (p *BasePet) PublishStatusEvent(ctx context.Context, publishFunc func(context.Context, *nostr.Event) error) error {
	p.mutex.RLock()
	state := p.state
	p.mutex.RUnlock()

	// Create status event
	evt := &nostr.Event{
		Kind:      30078,
		CreatedAt: nostr.Now(),
		Tags: nostr.Tags{
			{"d", "pet/status"},
			{"energy", fmt.Sprintf("%.1f", state.Energy)},
			{"happiness", fmt.Sprintf("%.1f", state.Happiness)},
			{"last_fed", state.LastFed.Format(time.UnixDate)},
			{"name", state.Name},
			{"state_emoji", p.GetStateEmoji()},
		},
		Content: fmt.Sprintf("Status update for pet: %s", state.Name),
	}

	return p.PublishEvent(ctx, evt, publishFunc)
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

// egg_pet.go
package main

import (
	"context"
	"fmt"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

// EggPet represents a pet in its initial state before naming
type EggPet struct {
	*BasePet
	ownerPubKey string
	createdAt   time.Time
}

// NewEggPet creates a new pet in egg state
func NewEggPet(ownerPubKey string) *EggPet {
	return &EggPet{
		BasePet:     NewBasePet("Egg"),
		ownerPubKey: ownerPubKey,
		createdAt:   time.Now(),
	}
}

// GetStateEmoji returns the emoji representing the current state
func (p *EggPet) GetStateEmoji() string {
	return "🥚"
}

// HandleNaming processes a naming event and transforms the egg into a proper pet
func (p *EggPet) HandleNaming(ctx context.Context, name string) Pet {
	fmt.Printf("Egg hatching into pet named: %s\n", name)

	// Create a proper pet with the given name
	pet := NewDefaultPet(name)

	// Copy any accumulated state from the egg
	pet.mutex.Lock()
	pet.state.Energy = p.state.Energy
	pet.state.Happiness = p.state.Happiness
	pet.mutex.Unlock()

	return pet
}

// Override BasePet methods for egg-specific behavior
func (p *EggPet) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Egg notified of event: %s\n", evt.ID)

	// Only respond to egg events with minor state changes
	// Full interaction will happen after naming
	p.mutex.Lock()
	p.state.Energy = min(100, p.state.Energy+0.5)
	p.mutex.Unlock()

	fmt.Print("Egg's state updated after event\n", currentState.Name)
}

// The egg responds minimally to other events
func (p *EggPet) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	// Minimal implementation for egg state
}

func (p *EggPet) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	// Minimal implementation for egg state
	return filter, nil
}

func (p *EggPet) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	// Minimal implementation for egg state
	return false, ""
}

// GetOwnerPubKey returns the public key of the pet's owner
func (p *EggPet) GetOwnerPubKey() string {
	return p.ownerPubKey
}

// GetCreationTime returns when the egg was created
func (p *EggPet) GetCreationTime() time.Time {
	return p.createdAt
}

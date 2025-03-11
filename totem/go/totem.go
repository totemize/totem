// totem.go
package main

import (
	"context"
	"fmt"
	"log"
	"sync"

	"github.com/nbd-wtf/go-nostr"
)

// Totem is the central manager that coordinates between relay and pets
type Totem struct {
	pubKey string
	pets   map[string]Pet
	mutex  sync.RWMutex
}

// NewTotem creates a new Totem instance
func NewTotem(pubKey string) *Totem {
	return &Totem{
		pubKey: pubKey,
		pets:   make(map[string]Pet),
	}
}

// RegisterPet adds a pet to the Totem's management
func (t *Totem) RegisterPet(p Pet) {
	t.mutex.Lock()
	defer t.mutex.Unlock()
	state := p.GetState()
	t.pets[state.Name] = p
	log.Printf("Pet registered: %s", state.Name)
}

// GetPubKey returns Totem's public key
func (t *Totem) GetPubKey() string {
	return t.pubKey
}

// handleStoreEvent notifies Totem and relevant pets about a new event
func (t *Totem) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of event: %s\n", evt.ID)

	// Check if the event is directed to a specific pet
	targetPet := t.findTargetPet(evt)

	if targetPet != nil {
		fmt.Printf("Notifying pet %s about event\n", targetPet.GetState().Name)
		targetPet.handleStoreEvent(ctx, evt)
	}

	// Log the event content
	fmt.Printf("Event content: %s\n", evt.Content)
}

// handleDeleteEvent notifies Totem and relevant pets about a deletion
func (t *Totem) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	fmt.Printf("Totem notified of deletion: %s\n", evt.ID)

	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		fmt.Printf("Notifying pet %s about deletion\n", targetPet.GetState().Name)
		targetPet.handleDeleteEvent(ctx, evt)
	}
}

// handleQueryEvents allows Totem to suggest modifications to query filters
func (t *Totem) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	modifiedFilter := filter

	t.mutex.RLock()
	defer t.mutex.RUnlock()

	// Let pets suggest filter modifications
	for _, pet := range t.pets {
		var err error
		modifiedFilter, err = pet.handleQueryEvents(ctx, modifiedFilter)
		if err != nil {
			return filter, nil // Ignore errors, use original filter
		}
	}

	return modifiedFilter, nil
}

// handleRejectEvent determines if an event should be rejected
func (t *Totem) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	fmt.Printf("Totem checking if event should be rejected: %s\n", evt.ID)

	// Check if any pet wants to reject this event
	targetPet := t.findTargetPet(evt)
	if targetPet != nil {
		return targetPet.handleRejectEvent(ctx, evt)
	}

	// No rejection by default
	return false, ""
}

// findTargetPet determines which pet should handle an event
func (t *Totem) findTargetPet(evt *nostr.Event) Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	// For this simple implementation, just return the first pet
	// In a real implementation, you'd have logic to determine the target
	// based on tags, content, etc.
	if len(t.pets) > 0 {
		for _, pet := range t.pets {
			return pet
		}
	}

	return nil
}

// GetPets returns all registered pets
func (t *Totem) GetPets() []Pet {
	t.mutex.RLock()
	defer t.mutex.RUnlock()

	pets := make([]Pet, 0, len(t.pets))
	for _, p := range t.pets {
		pets = append(pets, p)
	}

	return pets
}

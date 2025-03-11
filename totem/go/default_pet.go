// default_pet.go
package main

import (
	"context"
	"fmt"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

type DefaultPet struct {
	*BasePet
}

func NewDefaultPet(name string) *DefaultPet {
	return &DefaultPet{
		BasePet: NewBasePet(name),
	}
}

func (p *DefaultPet) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s notified of event: %s\n", currentState.Name, evt.ID)

	// Update pet state based on the event
	p.mutex.Lock()
	// Being fed (receiving events) costs energy
	p.state.Energy = max(0, p.state.Energy-1)
	// Happiness boost for short messages
	if len(evt.Content) < 100 {
		p.state.Happiness = min(100, p.state.Happiness+1)
	}
	// Update last fed time
	p.state.LastFed = time.Now()
	p.mutex.Unlock()

	fmt.Printf("Pet %s's state updated after event\n", currentState.Name)
}

func (p *DefaultPet) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s notified of delete event: %s\n", currentState.Name, evt.ID)

	// Update pet state based on the delete operation
	if currentState.Energy < 50 {
		p.mutex.Lock()
		// Energy boost from cleaning up
		p.state.Energy = min(100, p.state.Energy+2)
		p.mutex.Unlock()
	}

	fmt.Printf("Pet %s's state updated after delete event\n", currentState.Name)
}

func (p *DefaultPet) handleQueryEvents(ctx context.Context, filter nostr.Filter) (nostr.Filter, error) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s suggesting filter modifications\n", currentState.Name)

	// If pet is tired, it might suggest limiting the number of results
	if currentState.Energy < 30 && filter.Limit == 0 {
		filter.Limit = 10
		fmt.Printf("Pet %s is tired, suggesting to limit results to 10\n", currentState.Name)
	}

	// Update pet state for suggesting modifications
	p.mutex.Lock()
	p.state.Energy = max(0, p.state.Energy-0.1)
	p.mutex.Unlock()

	return filter, nil
}

func (p *DefaultPet) handleRejectEvent(ctx context.Context, evt *nostr.Event) (bool, string) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s checking if event should be rejected: %s\n", currentState.Name, evt.ID)

	// Pet might reject events if it's unhappy and the message is too long
	if currentState.Happiness < 50 && len(evt.Content) > 250 {
		reason := fmt.Sprintf("Pet %s is grumpy and doesn't like long messages", currentState.Name)
		return true, reason
	}

	return false, ""
}

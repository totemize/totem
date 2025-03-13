package main

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/nbd-wtf/go-nostr"
)

type DefaultPet struct {
	*BasePet
	totem *Totem
}

func NewDefaultPet(name string, totem *Totem) *DefaultPet {
	return &DefaultPet{
		BasePet: NewBasePet(name),
		totem:   totem,
	}
}

func (p *DefaultPet) handleStoreEvent(ctx context.Context, evt *nostr.Event) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s notified of event: %s\n", currentState.Name, evt.ID)

	p.mutex.Lock()

	p.state.Energy = min(100, p.state.Energy+5)
	p.state.Happiness = min(100, p.state.Happiness+2)

	p.state.LastFed = time.Now()
	p.mutex.Unlock()

	fmt.Printf("Pet %s's state updated after event\n", currentState.Name)
}

func (p *DefaultPet) publishMetadataEvent(ctx context.Context) {
	// Create metadata content
	metadata := map[string]string{
		"name":  p.state.Name,
		"about": fmt.Sprintf("I'm %s, a virtual pet living in this relay!", p.state.Name),
	}

	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		fmt.Printf("Error creating metadata JSON: %v\n", err)
		return
	}

	// Create the event with owner tag
	ev := nostr.Event{
		PubKey:    p.publicKey,
		CreatedAt: nostr.Now(),
		Kind:      nostr.KindProfileMetadata,
		Tags:      nostr.Tags{{"p", p.BasePet.ownerPubKey}},
		Content:   string(metadataJSON),
	}

	// Sign the event with the pet's private key
	ev.Sign(p.privateKey)

	// Publish through Totem
	fmt.Printf("Publishing metadata event for pet %s\n", p.state.Name)
	err = p.totem.PublishEvent(ctx, &ev)
	if err != nil {
		fmt.Printf("Error publishing metadata: %v\n", err)
	} else {
		fmt.Printf("Published metadata for pet %s with ID: %s\n", p.state.Name, ev.ID)
	}
}
func (p *DefaultPet) handleDeleteEvent(ctx context.Context, evt *nostr.Event) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	fmt.Printf("Pet %s notified of delete event: %s\n", currentState.Name, evt.ID)

	if currentState.Energy < 50 {
		p.mutex.Lock()
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

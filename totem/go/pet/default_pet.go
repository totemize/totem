package pet

import (
	"context"
	"fmt"

	"github.com/nbd-wtf/go-nostr"
)

type DefaultPet struct {
	*BasePet
}

func NewDefaultPet(name string, db Database) *DefaultPet {
	return &DefaultPet{
		BasePet: NewBasePet(name, db),
	}
}

func (p *DefaultPet) HandleStore(ctx context.Context, evt *nostr.Event) error {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	// Pet personality affecting storage
	if currentState.Energy < 99 {
		return fmt.Errorf("pet is too tired to store events right now")
	}

	if currentState.Happiness < 50 && len(evt.Content) > 250 {
		return fmt.Errorf("pet is grumpy and doesn't like long messages")
	}

	// Process the event
	err := p.database.SaveEvent(ctx, evt)
	if err == nil {
		p.mutex.Lock()
		// Energy cost for storing events
		p.state.Energy = max(0, p.state.Energy-1)
		// Happiness boost for short messages
		if len(evt.Content) < 100 {
			p.state.Happiness = min(100, p.state.Happiness+1)
		}
		p.mutex.Unlock()
	}
	return err
}

func (p *DefaultPet) HandleDelete(ctx context.Context, evt *nostr.Event) error {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	if currentState.Happiness > 90 {
		return fmt.Errorf("pet is too happy and doesn't want to delete anything")
	}

	err := p.database.DeleteEvent(ctx, evt)
	if err == nil && currentState.Energy < 50 {
		p.mutex.Lock()
		// Energy boost from cleaning up
		p.state.Energy = min(100, p.state.Energy+2)
		p.mutex.Unlock()
	}
	return err
}

func (p *DefaultPet) HandleQuery(ctx context.Context, filter nostr.Filter) (chan *nostr.Event, error) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	if currentState.Energy < 30 && filter.Limit == 0 {
		filter.Limit = 10 // Limit results when tired
	}

	events, err := p.database.QueryEvents(ctx, filter)
	if err == nil {
		p.mutex.Lock()
		p.state.Energy = max(0, p.state.Energy-0.5)
		p.mutex.Unlock()
	}
	return events, err
}

func (p *DefaultPet) HandleCount(ctx context.Context, filter nostr.Filter) (int64, error) {
	p.mutex.RLock()
	currentState := p.state
	p.mutex.RUnlock()

	if currentState.Energy < 10 {
		return 0, fmt.Errorf("pet is too exhausted to count events")
	}

	count, err := p.database.CountEvents(ctx, filter)
	if err == nil {
		p.mutex.Lock()
		p.state.Energy = max(0, p.state.Energy-0.1)
		p.mutex.Unlock()
	}
	return count, err
}

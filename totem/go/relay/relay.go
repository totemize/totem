package relay

import (
	"totem-core/pet"

	"github.com/fiatjaf/khatru"
)

type RelayInfo struct {
	Name        string
	Description string
	PubKey      string
	Software    string
	Version     string
}

type PetRelay struct {
	*khatru.Relay
	pet pet.Pet
}

func NewPetRelay(info RelayInfo, p pet.Pet) *PetRelay {
	relay := &PetRelay{
		Relay: khatru.NewRelay(),
		pet:   p,
	}

	// Configure relay info
	relay.Info.Name = info.Name
	relay.Info.Description = info.Description
	relay.Info.PubKey = info.PubKey
	relay.Info.Software = info.Software
	relay.Info.Version = info.Version

	// Connect pet handlers to relay operations
	relay.StoreEvent = append(relay.StoreEvent, p.HandleStore)
	relay.DeleteEvent = append(relay.DeleteEvent, p.HandleDelete)
	relay.QueryEvents = append(relay.QueryEvents, p.HandleQuery)
	relay.CountEvents = append(relay.CountEvents, p.HandleCount)

	return relay
}

func (r *PetRelay) GetPet() pet.Pet {
	return r.pet
}

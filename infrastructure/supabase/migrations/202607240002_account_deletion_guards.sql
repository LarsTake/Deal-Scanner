create trigger sellers_deletion_guard before delete on deal_scanner.sellers
for each row execute function deal_scanner.prevent_mutation();

create trigger listings_deletion_guard before delete on deal_scanner.listings
for each row execute function deal_scanner.prevent_mutation();
